# 勘誤與重現說明 / Errata and Reproducibility Notes

[中文](#中文) · [English](#english)

---

## 中文

本文件整理 2026-10 重新檢查專題時發現的問題。論文（`docs/papers/thesis.docx`、`docs/papers/thesis.md`）保留繳交時的原樣，不做修改，所有更正都記在這裡。

**檢查方式。** 用專案本機的 SQLite 資料庫（`database/ptt_data.db`，約 186 MB）、`data/` 下的中間檔與輸出檔，以及兩個微調模型，重新計算論文中的數字，並逐一比對產生數字的腳本。資料庫、CSV 與模型權重因為檔案大小與隱私沒有放進 repo，所以外部讀者目前無法從乾淨的 clone 重跑。下文的「證據」欄位會註明檔案位置，標示「本機」的檔案不在 repo 裡。

### 一、假設檢定結果總覽

| 假設 | 論文結論 | 重新檢查後 |
|---|---|---|
| H1 情緒結構在三期間不同 | 成立 | **部分成立。**衝擊期正面下降、中性上升，校正多重比較後仍顯著；但「暫緩期信心 V 型回復」不顯著。 |
| H2 情緒水準與累積報酬同步 | 成立，多空呈鏡像 | **方向寫反。**正面與負面都和大盤**同向**，只有中性反向。相關主要來自三個時期的平均水準不同。 |
| H3 兩日情緒動能最能反映反轉 | 成立，「48 小時共識」 | **不成立。**結果取決於 lag 的算法；照論文自己的定義（兩個日曆日）不顯著，且方向相反。 |
| H4 討論量與波動度正相關 | 成立 | **成立，但只是同日相關。**沒有預測下一個交易日波動的能力。 |

### 二、數字或描述寫錯的地方

| 項目 | 論文寫的 | 實際 | 證據 |
|---|---|---|---|
| 事件描述（摘要、1.1、5.7） | 美中關稅，由宣布到暫緩 | 美國 2025/4/2（台灣時間 4/3）宣布**對等關稅**，台灣 32%。4/9 宣布的 90 天暫緩**排除中國**，同日對中國關稅提高到 125%。 | 公開新聞報導 |
| 留言 Fleiss' Kappa（表 3-1） | 0.6509（Substantial） | **0.5509（Moderate）**；標題 0.2377、內文 0.4452 正確 | `scripts/kappa.ipynb` 輸出（本機） |
| 三人皆不同的樣本（3.3.2） | 予以排除 | 經仲裁後以 `agree_n=3` 寫回共識表，300 則留言全數收錄；仲裁者沒有紀錄 | `scripts/arbitrate_and_insert.py:10, 88-96` |
| V2 資料集（表 3-2） | 訓練 750（每類 250）、驗證 120（每類 40）；內文又寫 8:1:1 | 訓練 **493**（負 185／中 159／正 149），驗證 **90**（每類 30），測試 210（每類 70） | DB 表 `v2_training_set_master`、`v2_validation_set_master`、`manual_test_set`（本機） |
| 訓練設定（3.3.3） | 從 nlptown 微調；batch 16、lr 2e-5、4 epochs | V1：batch 8、lr 5e-5（預設）、3 epochs，最後選 epoch 1。V2：**從 V1 權重接續**，batch 32、lr 2e-5、設定 8 epochs，最終權重為 epoch 6 | `scripts/finetune_bert.py:119-127`、`scripts/finetune_v2_push_extra.py:22, 126-129`、`checkpoint-96/trainer_state.json`（本機） |
| V1 失敗原因（3.3.4） | 雜訊與資料不平衡 | 主要是 checkpoint 選擇。同一次訓練的 epoch 3 在 gold 測試集 macro-F1 = 0.523，已高於 V0 的 0.475 | `nlptown-finetuned-on-ptt/checkpoint-159`（本機） |
| 資料清洗（3.3.1） | 同人同分鐘合併後剩 392,413 則 | 專案中沒有實作「同人同分鐘合併」的程式；分析實際使用 **398,525** 則 | `data/outputs/THESIS_FULL_TABLES.txt`（本機） |
| 爬蟲統計（3.3.1） | 4,080 篇、432,167 則 | 這是整個資料庫的數量。研究期間 3/27–4/16 內為 3,878 篇、408,435 則 | DB 表 `sentiments`、`push_comments`（本機） |
| H2 負面情緒（4.3.2） | ρ = −0.560 | **ρ = +0.560**，p = 0.046 | `data/outputs/thesis_full_stats_report.txt`（本機）；重算 |
| 表 4-4 樣本數 | N = 13 | 各列不同：Lag-1 N=12、Lag-2 N=11、Lag-3 N=10、Lag-4 N=9 | `data/outputs/momentum_sensitivity_report.txt`（本機） |
| 表 4-4 Lag-1 | p = 0.665 | p = 0.681（N=12） | 同上 |
| 表 4-4 Lag-4 | ρ = 0.215，p = 0.4500 | ρ = 0.200，p = 0.606 | 同上；圖 4-6 本身標示 0.20 |
| 表 4-1 報酬樣本數 | 各期 N = 7 | 報酬只有交易日：5／3／5 天。表中是日報酬平均，不是期間累積報酬 | `data/raw/final_prop_surge_data.csv`（本機） |
| 4.4.1 | 與「隔日」漲跌無關 | 實際檢定的是**同日**報酬 | `scripts/run_momentum_sensitivity.py` |
| 3/27 報酬 | — | 部分分析把 3/27 報酬填為 0（實際 −1.386%），影響 H4、圖 4-1 至 4-5 | `scripts/run_final_prop_surge_analysis.py:62` |
| H4 討論量 vs 波動度（4.5.2、表 4-5） | ρ = 0.736 | 修正 3/27 後 **ρ = 0.714，p = 0.006** | 重算 |
| 4.6.2 Log Volume 穩健性檢定 | 結果一致，證實穩健 | Spearman 只看排序，取 log 不改變排序，結果必然相同，不構成穩健性證據 | — |
| 事後比較（表 4-3） | 未說明方法 | 為 Welch t 檢定，未做多重比較校正（見第三節） | `scripts/run_full_7day_analysis.py` |
| 其他 | — | 4/07 討論量為 P1 均值的 4.18 倍（論文 4.1）；「中性 +14.6%」為相對變化（絕對 +4.8 個百分點）；Lag-3 p = 0.0816（論文 0.0820）；有兩張圖都編號 4-5；內文殘留「圖 19」 | — |

### 三、影響結論解讀的問題

**H1：結構變化只有一部分站得住。**三組的變異數相差約 3 倍，而且每日比例有自相關（lag-1 約 0.38–0.48）。改用 Welch ANOVA 時，正／負／中性 p = 0.077／0.055／0.052。用 Tukey HSD 做事後比較：

- 仍顯著：P1→P2 正面下降（p = 0.020）、P1→P2 中性上升（p = 0.023）、P1→P3 負面下降（p = 0.007）、P1→P3 中性上升（p = 0.015）。
- 不顯著：P2→P3 正面回升（p = 0.222）、負面下降（p = 0.142）、中性變化（p = 0.974）。因此「信心 V 型回復」與「中性階梯式上升」都沒有統計支持。

**H2：不是多空鏡像。**交易日 N = 13 時，正面 ρ = +0.588（p = 0.035）、負面 ρ = +0.560（p = 0.046）、中性 ρ = −0.484（p = 0.094）。真正隨大盤變動的是「中性比例的消長」。此外，累積報酬是有趨勢的序列，改用每日變化量時，正面情緒變化對日報酬只有 ρ = 0.133（p = 0.68）。相關主要來自三個時期的平均水準差異。

**H3：Lag-2 是算法選擇的結果。**

- 論文的 0.782 是先刪掉非交易日，再跟「兩個交易日前」比。在連假前後，這實際上相隔 2 到 6 個日曆日，11 筆中只有 5 筆真的相隔 2 天，所以「48 小時」沒有資料依據。
- 照論文自己的定義（跟兩個日曆日前比），ρ = −0.255，p = 0.450（`scripts/step2_statistical_analysis.py` 的輸出 `data/outputs/THESIS_FULL_STATS.txt:39`，本機）。
- 專案腳本試過 Lag 1–5 × 正／負 × 兩種定義，以及多種情緒指標，論文只報告其中表現最好的一組。以置換檢定校正「從 Lag 1–5 挑最大值」後，p ≈ 0.067。

**「預測力」「反轉訊號」「預警」沒有被檢定過。**所有相關都是同一天的情緒對同一天的報酬。交易日留言有 52.8% 是 13:30 收盤之後才發的，因此也可能是 PTT 在反應當天盤勢。補做的領先檢定都不顯著：Lag-2 動能對隔日報酬 ρ = 0.091（p = 0.80），討論量對隔日絕對報酬 ρ = 0.168（p = 0.60）。專案中曾做過「隔夜情緒對當日報酬」的檢定，結果不顯著，論文沒有報告。

**交易日分析丟掉了衝擊當下的討論。**N = 13 的分析直接排除非交易日的留言：116,999 則，占 29.4%，其中 4/3–4/6 連假期間有 84,148 則，正是關稅消息剛出來的時候。

**模型評估：測試集與訓練資料有重疊，且模型是看著測試集分數調整的。**

- 2025-11-14 下午，V2 至少重新訓練 7 次，每次訓練結束都在 gold 測試集上評分（`scripts/finetune_v2_push_extra.py:153-174`）；同一段時間內新增約 30 筆「人工精選」訓練資料，16:55 才一次匯入 210 筆 gold 測試集。
- 210 筆 gold 中有 26 筆在 V2 訓練或驗證集裡有近似重複（字串相似度 ≥ 0.75），其中 24 筆標籤相同。例：訓練集「同感，可能很多人都太年輕了」（資料庫原文），測試集「同感，很多人都太年輕了」。
- V2 在這 26 筆上的準確率為 0.846，其餘 184 筆為 0.663。排除這 26 筆後，macro-F1 由 0.683 降為 0.656。
- 在由三人共識標註、未參與調整的 push-only 測試切分（45 筆）上，V2 macro-F1 為 0.580。
- 表 3-3 的數字本身可以用本機模型完整重現，但它高估了模型在未見資料上的表現。

**標註信度的適用範圍。**Kappa 是在 300 則留言上算的，這 300 則來自 3 個討論串的連續留言，不是隨機抽樣。V2 訓練集 493 筆中只有 183 筆、gold 測試集 210 筆中只有 1 筆來自三人標註，其餘為單人標註。

### 四、站得住的部分

- 表 3-3 的 V0／V1／V2 指標可在 gold 測試集上完整重現（但請見上面的重疊問題）。
- 表 4-1 的描述統計、表 4-2 的 ANOVA F／p／η²、H2 正面情緒 ρ = 0.588、Lag-2 在交易日算法下的 ρ = 0.782、Bootstrap（seed 42）皆可完整重現。
- 統計分析確實使用 V2 模型的預測（DB 表 `ai_model_predictions_v2_push_only`，421,528 則），標籤編號（0 = 負、1 = 中、2 = 正）在整個流程中一致。
- 衝擊期正面下降、中性上升，校正後仍然顯著。
- 討論量與波動度的同日相關（ρ = 0.714，p = 0.006）成立。

### 五、目前的重現狀態

- `run_pipeline.py` 預設讀 `database/ptt_data_m.db`，但本機檔名是 `database/ptt_data.db`，需要用 `.env` 的 `DB_PATH_M` 指定。
- 2026-02 搬移目錄後，`scripts/` 中多數腳本仍使用舊的相對路徑，無法直接執行。
- `data/raw/thesis_final_data.csv` 的表頭在「收盤價」欄位損壞，導致之後的欄名錯位。
- `src/pipeline/thesis_stats.py` 的 bootstrap 沒有固定 random seed，每次 CI 略有不同。
- `kappa.ipynb` 等 notebook 被 `.gitignore` 排除，沒有進版控。

本勘誤整理於 2026-10-14。

---

## English

This document records problems found when the project was re-checked in October 2026. The thesis (`docs/papers/thesis.docx`, `docs/papers/thesis.md`) is kept exactly as submitted; all corrections live here.

**How this was checked.** Numbers in the thesis were recomputed from the project's local SQLite database (`database/ptt_data.db`, about 186 MB), the intermediate and output files under `data/`, and the two fine-tuned models, and each number was traced back to the script that produced it. The database, CSV files and model weights are not in this repository because of size and privacy, so readers cannot currently rerun the analysis from a clean clone. Files marked "local" in the evidence column are not in the repository.

### 1. Hypotheses at a glance

| Hypothesis | Thesis conclusion | After re-checking |
|---|---|---|
| H1 Sentiment composition differs across periods | Supported | **Partly.** The shock-week fall in positive share and rise in neutral share survive multiple-comparison correction. The "V-shaped recovery of confidence" in the suspension period does not. |
| H2 Sentiment level moves with cumulative return | Supported; bullish and bearish shares mirror each other | **Direction misreported.** Positive and negative shares both move **with** the index; only neutral moves against it. The correlation mostly reflects different average levels across the three periods. |
| H3 Two-day sentiment momentum best captures reversals | Supported; "48-hour consensus" | **Not supported.** The result depends on how the lag is counted. Under the thesis's own definition (two calendar days) it is not significant and has the opposite sign. |
| H4 Discussion volume correlates with volatility | Supported | **Supported as a same-day association only.** It does not predict next-day volatility. |

### 2. Reporting errors

| Item | Thesis says | Actual | Evidence |
|---|---|---|---|
| Event (abstract, 1.1, 5.7) | U.S.–China tariffs, announced then paused | The U.S. announced **reciprocal tariffs** on 2 April 2025 (3 April Taiwan time), 32% on Taiwan. The 90-day pause on 9 April **excluded China**; the China rate rose to 125% the same day. | News coverage |
| Comment Fleiss' kappa (Table 3-1) | 0.6509 (substantial) | **0.5509 (moderate)**. Title 0.2377 and post body 0.4452 are correct. | `scripts/kappa.ipynb` output (local) |
| Items where all three annotators disagreed (3.3.2) | Excluded | Arbitrated and written back with `agree_n=3`; all 300 comments were kept. The arbitrator is not recorded. | `scripts/arbitrate_and_insert.py:10, 88-96` |
| V2 dataset (Table 3-2) | Train 750 (250 per class), validation 120 (40 per class); text also says 8:1:1 | Train **493** (neg 185 / neu 159 / pos 149), validation **90** (30 per class), test 210 (70 per class) | DB tables `v2_training_set_master`, `v2_validation_set_master`, `manual_test_set` (local) |
| Training setup (3.3.3) | Fine-tuned from nlptown; batch 16, lr 2e-5, 4 epochs | V1: batch 8, lr 5e-5 (default), 3 epochs, epoch 1 kept. V2: **continued from V1 weights**, batch 32, lr 2e-5, 8 epochs configured, final weights from epoch 6 | `scripts/finetune_bert.py:119-127`, `scripts/finetune_v2_push_extra.py:22, 126-129`, `checkpoint-96/trainer_state.json` (local) |
| Why V1 failed (3.3.4) | Noise and class imbalance | Mainly checkpoint selection. The epoch-3 checkpoint from the same run scores macro-F1 0.523 on the gold test set, above V0's 0.475. | `nlptown-finetuned-on-ptt/checkpoint-159` (local) |
| Cleaning (3.3.1) | 392,413 comments after merging same user within the same minute | No code implements that merge; the analysis uses **398,525** comments | `data/outputs/THESIS_FULL_TABLES.txt` (local) |
| Crawl counts (3.3.1) | 4,080 posts, 432,167 comments | Those are whole-database totals. Inside 27 Mar–16 Apr: 3,878 posts, 408,435 comments | DB tables `sentiments`, `push_comments` (local) |
| H2 negative share (4.3.2) | ρ = −0.560 | **ρ = +0.560**, p = 0.046 | `data/outputs/thesis_full_stats_report.txt` (local); recomputed |
| Table 4-4 sample size | N = 13 | Varies by row: Lag-1 N=12, Lag-2 N=11, Lag-3 N=10, Lag-4 N=9 | `data/outputs/momentum_sensitivity_report.txt` (local) |
| Table 4-4 Lag-1 | p = 0.665 | p = 0.681 (N=12) | Same |
| Table 4-4 Lag-4 | ρ = 0.215, p = 0.4500 | ρ = 0.200, p = 0.606 | Same; Figure 4-6 itself shows 0.20 |
| Table 4-1 return sample size | N = 7 per period | Returns exist only on trading days: 5 / 3 / 5. Values are mean daily returns, not period returns. | `data/raw/final_prop_surge_data.csv` (local) |
| 4.4.1 | No link to the *next-day* move | The test used the **same-day** return | `scripts/run_momentum_sensitivity.py` |
| 27 March return | — | Some analyses set it to 0 (actual −1.386%), affecting H4 and Figures 4-1 to 4-5 | `scripts/run_final_prop_surge_analysis.py:62` |
| H4 volume vs volatility (4.5.2, Table 4-5) | ρ = 0.736 | **ρ = 0.714, p = 0.006** after fixing 27 March | Recomputed |
| 4.6.2 log-volume robustness check | Same result, so robust | Spearman uses ranks only and a log does not change ranks, so the result is identical by construction. It is not robustness evidence. | — |
| Post-hoc tests (Table 4-3) | Method not stated | Welch t-tests with no multiple-comparison correction (see section 3) | `scripts/run_full_7day_analysis.py` |
| Minor | — | 7 April volume was 4.18× the P1 mean (thesis: 4.1); "neutral +14.6%" is a relative change (+4.8 percentage points); Lag-3 p = 0.0816 (thesis: 0.0820); two figures are numbered 4-5; the text still cites "Figure 19" | — |

### 3. Problems that change the interpretation

**H1: only part of the structural change holds.** Group variances differ by about 3×, and daily shares are autocorrelated (lag-1 about 0.38–0.48). With Welch's ANOVA, p = 0.077 / 0.055 / 0.052 for positive / negative / neutral. Tukey HSD post-hoc results:

- Still significant: positive down P1→P2 (p = 0.020), neutral up P1→P2 (p = 0.023), negative down P1→P3 (p = 0.007), neutral up P1→P3 (p = 0.015).
- Not significant: positive rebound P2→P3 (p = 0.222), negative fall P2→P3 (p = 0.142), neutral change P2→P3 (p = 0.974). The "V-shaped recovery of confidence" and the "step-wise rise in neutral sentiment" are not supported.

**H2: not a bull/bear mirror.** On the 13 trading days, positive ρ = +0.588 (p = 0.035), negative ρ = +0.560 (p = 0.046), neutral ρ = −0.484 (p = 0.094). What moves with the index is the neutral share. Cumulative return also trends, and in daily changes the positive-share change against daily return is only ρ = 0.133 (p = 0.68). The correlation mostly comes from the three periods sitting at different average levels.

**H3: the Lag-2 result comes from a counting choice.**

- The thesis's 0.782 drops non-trading days first and then compares with the value "two trading days earlier". Around the holiday that spans 2 to 6 calendar days, and only 5 of the 11 pairs are actually 2 days apart, so the "48 hours" reading has no basis in the data.
- Under the thesis's own definition (two calendar days earlier), ρ = −0.255, p = 0.450 (output of `scripts/step2_statistical_analysis.py`, `data/outputs/THESIS_FULL_STATS.txt:39`, local).
- The scripts tried Lag 1–5 × positive/negative × two lag definitions plus several sentiment indicators, and the thesis reports the best one. A permutation test that accounts for picking the largest of Lag 1–5 gives p ≈ 0.067.

**"Predictive power", "reversal signal" and "early warning" were never tested.** Every correlation pairs same-day sentiment with same-day return, and 52.8% of trading-day comments were posted after the 13:30 close, so PTT may simply be reacting to the day's market. Lead tests are not significant: Lag-2 momentum vs next-day return ρ = 0.091 (p = 0.80); volume vs next-day absolute return ρ = 0.168 (p = 0.60). The project did test overnight sentiment against the same-day return; it was not significant and was not reported.

**The trading-day analysis drops the shock itself.** The N = 13 analyses exclude comments from non-trading days: 116,999 comments (29.4%), including 84,148 from the 3–6 April holiday, exactly when the tariff news broke.

**Model evaluation: the test set overlaps the training data, and the model was tuned against test scores.**

- On the afternoon of 14 November 2025, V2 was retrained at least 7 times and each run was scored on the gold test set (`scripts/finetune_v2_push_extra.py:153-174`). About 30 hand-picked training items were added in the same window, and the 210 gold test items were imported at 16:55.
- 26 of the 210 gold items have near-duplicates (string similarity ≥ 0.75) in the V2 train or validation set, 24 with the same label. Example: train has "同感，可能很多人都太年輕了" (the original database comment); test has "同感，很多人都太年輕了".
- V2 accuracy is 0.846 on those 26 items and 0.663 on the other 184. Excluding them lowers macro-F1 from 0.683 to 0.656.
- On the 45-item push-only test split, labeled by three-annotator consensus and not used for tuning, V2 macro-F1 is 0.580.
- Table 3-3 itself reproduces exactly with the local models, but it overstates performance on unseen data.

**What the agreement score covers.** Kappa was computed on 300 comments taken as consecutive replies from 3 threads, not a random sample. Only 183 of the 493 V2 training items and 1 of the 210 gold test items came from the three-annotator procedure; the rest were labeled by one person.

### 4. What holds up

- Table 3-3 (V0 / V1 / V2) reproduces exactly on the gold test set (see the overlap issue above).
- Table 4-1, Table 4-2 ANOVA F / p / η², H2 positive ρ = 0.588, Lag-2 ρ = 0.782 under the trading-day definition, and the bootstrap (seed 42) all reproduce exactly.
- The statistics do use V2 predictions (DB table `ai_model_predictions_v2_push_only`, 421,528 comments), and label ids (0 = negative, 1 = neutral, 2 = positive) are consistent across the pipeline.
- The shock-week fall in positive share and rise in neutral share remain significant after correction.
- The same-day volume–volatility association (ρ = 0.714, p = 0.006) holds.

### 5. Current reproducibility

- `run_pipeline.py` reads `database/ptt_data_m.db` by default, but the local file is `database/ptt_data.db`; set `DB_PATH_M` in `.env`.
- After the February 2026 directory move, most scripts in `scripts/` still use old relative paths and do not run as-is.
- The header of `data/raw/thesis_final_data.csv` is corrupted at the closing-price column, shifting the names of the columns after it.
- The bootstrap in `src/pipeline/thesis_stats.py` has no fixed random seed, so its intervals change slightly between runs.
- `kappa.ipynb` and the other notebooks are excluded by `.gitignore` and are not under version control.

Prepared 2026-10-14.
