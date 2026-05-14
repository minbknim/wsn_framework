/* amcp_e_params.h — AMCP-E 프로토콜 파라미터 (자동 생성)
 * 생성: WSN Framework v8 CCodeGenerator
 * 대상 HW: TelosB
 * 주의: 직접 수정하지 마세요. Python 파라미터에서 재생성 가능.
 */
#ifndef AMCP_E_PARAMS_H
#define AMCP_E_PARAMS_H

#include <stdint.h>

/* ── 네트워크 파라미터 ──────────────────────────────────────── */
#define WSN_N_NODES         100
#define WSN_AREA_X_M        100f
#define WSN_AREA_Y_M        100f
#define WSN_BS_X_M          50f
#define WSN_BS_Y_M          50f

/* ── 에너지 파라미터 (HW 보정값) ────────────────────────────── */
#define E0_J                0.5f        /* 초기 에너지 (J) */
#define E_ELEC_J_BIT        5e-08ef  /* 전자 회로 에너지 (J/bit) */
#define EPS_FS_J_BIT_M2     1e-11ef  /* 자유공간 증폭 (J/bit/m²) */
#define EPS_MP_J_BIT_M4     1.3e-15ef  /* 다중경로 증폭 (J/bit/m⁴) */
#define E_AGG_J_BIT         5e-09ef   /* 집계 에너지 (J/bit) */
#define D0_M                87.7f       /* 임계 거리 (m) */

/* ── AMCP-E 알고리즘 파라미터 ───────────────────────────────── */
#define AMCP_CH_RATIO       0.05f
#define AMCP_RESET_K        500U
#define AMCP_GAMMA          0.0f
#define AMCP_DIFF_TX        1   /* 차분전송 활성화 */
#define AMCP_E_MIN_RATIO    0.05f
#define AMCP_W_DIST         0.5f
#define AMCP_W_ENERGY       0.5f

/* ── 패킷 크기 ──────────────────────────────────────────────── */
#define PKT_DATA_BITS       4000U
#define PKT_CTRL_BITS       200U

/* ── HW 프로파일 ─────────────────────────────────────────────── */
#define HW_PROFILE          "TelosB"
#define HW_SUPPLY_V         3.0f
#define HW_TX_MA            17.4f
#define HW_RX_MA            18.8f
#define HW_SLEEP_MA         0.0051f
#define HW_DATA_RATE_KBPS   250.0f

#endif /* AMCP_E_PARAMS_H */
