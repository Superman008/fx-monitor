# fx-monitor 汇率看板

线上地址：https://superman008.github.io/fx-monitor/
仓库：https://github.com/Superman008/fx-monitor

- 采集口径：中行折算价（人民币/100 美元、人民币/100 澳元）；Moneychain「澳元 → 人民币」VIP 行现汇卖出价、「美金 → 人民币」现汇卖出价。
- 更新频率：周一至周五墨尔本时间 09:00–17:59，每小时第 7 分钟由 GitHub Actions 自动采集（cron `7 * * * *`，脚本内按墨尔本时间二次判定）。
- 采集失败时页面顶部会显示红色告警并保留上次成功数据；Moneychain 若认不出 VIP 行会拒绝发布，并把页面快照写到 `debug/`。

## 首次部署步骤（已执行，留档备查，约 15 分钟）

1. 注册/登录 github.com，新建仓库，名字例如 `fx-monitor`（Pages 免费版要求仓库为 Public）。
2. 把本文件夹里的所有内容上传到仓库，注意要包含隐藏文件夹 `.github`（建议用 GitHub Desktop，或网页上直接拖拽整个文件夹）。
3. 仓库 Settings → Pages：Source 选 "Deploy from a branch"，Branch 选 `main`，文件夹选 `/docs`，保存。
4. 仓库 Settings → Actions → General → Workflow permissions：选 "Read and write permissions"，保存。
5. 仓库 Actions 页 → 左侧选 `update-fx` → Run workflow → 勾选 force → 运行，先手动跑一次。
6. 约 1–2 分钟后打开 `https://你的用户名.github.io/fx-monitor/`，收藏即可。

运行失败时，把 Actions 日志里的报错，以及仓库 `debug/` 文件夹里的文件发给我。
