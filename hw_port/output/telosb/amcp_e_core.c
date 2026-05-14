/* amcp_e_core.c — AMCP-E 체인 구성 핵심 로직 (자동 생성, Contiki-NG 호환)
 *
 * 포팅 가이드:
 *   1. wsn_node_t 구조체를 플랫폼 노드 표현에 맞게 수정
 *   2. wsn_random_float()을 플랫폼 RNG로 교체
 *   3. wsn_log()를 UART/시리얼 출력으로 교체
 *   4. Contiki-NG: PROCESS_THREAD 내에서 amcp_e_round() 호출
 */
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "amcp_e_core.h"
#include "amcp_e_params.h"
#include "energy_model.h"

/* ── 플랫폼 추상화 (이식 시 수정) ─────────────────────────── */
#ifndef WSN_LOG
  #define WSN_LOG(fmt, ...) /* printf(fmt, ##__VA_ARGS__) */
#endif
#ifndef WSN_RANDOM_FLOAT
  #include <stdlib.h>
  #define WSN_RANDOM_FLOAT() ((float)rand() / RAND_MAX)
#endif

/* ── 내부 상태 ─────────────────────────────────────────────── */
static wsn_node_t g_nodes[WSN_N_NODES];
static uint8_t    g_chain_head[WSN_N_NODES];  /* 체인 헤드 인덱스 */
static uint16_t   g_round = 0;
static uint16_t   g_reset_counter = 0;
static float      g_last_sent[WSN_N_NODES];   /* 차분전송용 마지막 전송값 */

/* ── 초기화 ─────────────────────────────────────────────────── */
void amcp_e_init(const float* init_energies, const float* xs, const float* ys) {{
    for (int i = 0; i < WSN_N_NODES; i++) {{
        g_nodes[i].id     = i;
        g_nodes[i].energy = (init_energies) ? init_energies[i] : E0_J;
        g_nodes[i].x      = xs[i];
        g_nodes[i].y      = ys[i];
        g_nodes[i].alive  = 1;
        g_last_sent[i]    = -9999.0f;
    }}
    g_round = 0;
    g_reset_counter = 0;
    memset(g_chain_head, 0xFF, sizeof(g_chain_head));
}}

/* ── 헤드 선택 ──────────────────────────────────────────────── */
static int select_chain_heads(uint8_t k) {{
    float total_e = 0.0f;
    uint8_t n_alive = 0;
    for (int i = 0; i < WSN_N_NODES; i++) {{
        if (g_nodes[i].alive) {{ total_e += g_nodes[i].energy; n_alive++; }}
    }}
    if (n_alive == 0) return 0;

    memset(g_chain_head, 0xFF, sizeof(g_chain_head));
    uint8_t n_heads = 0;
    for (int i = 0; i < WSN_N_NODES && n_heads < k; i++) {{
        if (!g_nodes[i].alive) continue;
        float prob = (AMCP_CH_RATIO * g_nodes[i].energy) / (total_e / n_alive + 1e-12f);
        if (WSN_RANDOM_FLOAT() < prob) {{
            g_chain_head[n_heads++] = i;
        }}
    }}
    /* 헤드 부족 시 에너지 최대 노드로 보완 */
    if (n_heads == 0) {{
        int best = -1; float best_e = -1.0f;
        for (int i = 0; i < WSN_N_NODES; i++) {{
            if (g_nodes[i].alive && g_nodes[i].energy > best_e) {{
                best_e = g_nodes[i].energy; best = i;
            }}
        }}
        if (best >= 0) g_chain_head[n_heads++] = best;
    }}
    return n_heads;
}}

/* ── 한 라운드 실행 ─────────────────────────────────────────── */
amcp_e_result_t amcp_e_round(float* sense_values) {{
    amcp_e_result_t res = {{0}};
    g_round++;
    g_reset_counter++;

    /* K 결정 */
    uint8_t k = (uint8_t)(AMCP_CH_RATIO * WSN_N_NODES);
    if (k < 1) k = 1;
    if (g_reset_counter >= AMCP_RESET_K) {{
        g_reset_counter = 0;
        k = k * 2;  /* 리셋 시 K 일시 증가 */
    }}

    int n_heads = select_chain_heads(k);
    res.n_heads = n_heads;

    /* 멤버 → 헤드 전송 */
    for (int i = 0; i < WSN_N_NODES; i++) {{
        if (!g_nodes[i].alive) continue;
        res.n_generated++;

        /* 차분전송 필터 */
        float sv = sense_values ? sense_values[i] : 0.0f;
#if AMCP_DIFF_TX
        if (fabsf(sv - g_last_sent[i]) < 0.01f) continue;  /* 변화 없으면 억제 */
        g_last_sent[i] = sv;
#endif

        /* 가장 가까운 헤드 탐색 */
        float min_dist = 1e9f; int best_head = -1;
        for (int h = 0; h < n_heads; h++) {{
            int hi = g_chain_head[h];
            if (hi == 0xFF || !g_nodes[hi].alive) continue;
            float d = wsn_dist(g_nodes[i].x, g_nodes[i].y,
                               g_nodes[hi].x, g_nodes[hi].y);
            if (d < min_dist) {{ min_dist = d; best_head = hi; }}
        }}
        if (best_head < 0) continue;

        float e_tx = wsn_tx_energy(PKT_DATA_BITS, min_dist);
        g_nodes[i].energy -= e_tx;
        if (g_nodes[i].energy <= 0.0f) {{ g_nodes[i].alive = 0; continue; }}
        res.n_delivered++;
    }}

    /* 헤드 → BS 전송 */
    for (int h = 0; h < n_heads; h++) {{
        int hi = g_chain_head[h];
        if (hi == 0xFF || !g_nodes[hi].alive) continue;
        float d_bs = wsn_dist(g_nodes[hi].x, g_nodes[hi].y, WSN_BS_X_M, WSN_BS_Y_M);
        float e_agg = wsn_agg_energy(PKT_DATA_BITS * (WSN_N_NODES / k));
        float e_tx  = wsn_tx_energy(PKT_DATA_BITS, d_bs);
        g_nodes[hi].energy -= (e_agg + e_tx);
        if (g_nodes[hi].energy <= 0.0f) g_nodes[hi].alive = 0;
    }}

    /* 생존 노드 수 집계 */
    for (int i = 0; i < WSN_N_NODES; i++)
        if (g_nodes[i].alive) res.n_alive++;

    res.round = g_round;
    WSN_LOG("Round %u: alive=%u delivered=%u/%u\n",
            g_round, res.n_alive, res.n_delivered, res.n_generated);
    return res;
}}

/* ── 상태 조회 ──────────────────────────────────────────────── */
const wsn_node_t* amcp_e_get_nodes(void) {{ return g_nodes; }}
uint16_t amcp_e_get_round(void) {{ return g_round; }}
