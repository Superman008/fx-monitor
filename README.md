# 汇率看板部署步骤（约 15 分钟）

1. 注册/登录 github.com，新建仓库，名字例如 `fx-monitor`（Pages 免费版要求仓库为 Public）。
2. 把本文件夹里的所有内容上传到仓库，注意要包含隐藏文件夹 `.github`（建议用 GitHub Desktop，或网页上直接拖拽整个文件夹）。
3. 仓库 Settings → Pages：Source 选 "Deploy from a branch"，Branch 选 `main`，文件夹选 `/docs`，保存。
4. 仓库 Settings → Actions → General → Workflow permissions：选 "Read and write permissions"，保存。
5. 仓库 Actions 页 → 左侧选 `update-fx` → Run workflow → 勾选 force → 运行，先手动跑一次。
6. 约 1–2 分钟后打开 `https://你的用户名.github.io/fx-monitor/`，收藏即可。

运行失败时，把 Actions 日志里的报错，以及仓库 `debug/` 文件夹里的文件发给我。
