# Mataroa × GitHub Bridge

用 GitHub 幫你的 [Mataroa](https://mataroa.blog/) 部落格建立文章備份，也可以先在 GitHub 寫 Markdown，再手動把新文章發布到 Mataroa。

本專案使用 Python 標準庫，不需要安裝第三方套件，也不需要租用伺服器。日常工作由 GitHub Actions 執行。

> [!IMPORTANT]
> **公開原始碼倉庫不應存放你的私人文章，也不要在公開倉庫設定真實的 `MATAROA_API_KEY` 或執行備份工作流。** 備份工作流會把文章內容提交到正在執行它的 GitHub 倉庫；如果倉庫是公開的，文章也可能公開。請把公開倉庫只當作原始碼展示頁，實際使用時另建一個 **Private（私有）** 倉庫。

## 這個工具能做什麼？

- **每日備份：** 從 Mataroa 讀取文章，存成 `posts/` 裡的 Markdown 檔案。
- **手機寫作：** 在 GitHub 網頁或手機 App 編輯 `drafts/` 裡的 Markdown 草稿。
- **手動發布：** 你在 GitHub Actions 手動啟動發布工作流、指定草稿後，才會嘗試把新文章發布到 Mataroa。
- **保留版本：** 備份有變更時，GitHub Actions 會提交更新；Git 的提交歷史可用來查看舊版本。
- **避免意外重複發布：** 程式會在草稿中保存穩定識別碼，並在發布前檢查 Mataroa，處理部分網路錯誤或工作流中斷的情況。

### 重要限制

- 目前只支援**新增文章**。如需修改已有文章，請直接在 Mataroa 編輯；之後的備份會更新 `posts/` 中的副本。
- 備份範圍是 Mataroa 的文章（posts），不包括自訂頁面、留言，也不會獨立下載圖片檔。文章中的圖片 URL 會保留，但這不代表圖片本身已獲備份。
- 程式不會因為某篇文章不再出現在 Mataroa API 回應中，就自動刪除 `posts/` 裡的檔案。
- 本工具不能取代你在 Mataroa 或其他位置另外保存的備份。

## 開始前先了解資料夾

| 路徑 | 用途 |
|---|---|
| `posts/` | 從 Mataroa API 備份下來的文章，以線上版本為準。 |
| `drafts/` | 等待發布的新文章。 |
| `published/` | 經此工具發布後，保存的草稿副本。它與 `posts/` 用途不同，因此可能有同一篇文章的兩份檔案。 |
| `scripts/mataroa_sync.py` | 備份、草稿驗證與發布的主要程式。 |
| `.github/workflows/backup.yml` | 每日自動備份工作流，也可以手動啟動。 |
| `.github/workflows/publish.yml` | 手動發布指定草稿的工作流。 |
| `tests/` | 不需要連接 Mataroa 的單元測試。 |

## 實際使用：請在私有倉庫部署

公開倉庫適合分享程式碼；你的文章備份則應放在另一個私有倉庫。下面的部署步驟請在**新建的 Private 倉庫**進行，不要直接在公開的原始碼倉庫操作。

### 第 1 步：建立私有倉庫

1. 在 GitHub 建立一個新倉庫，例如 `mataroa-github-bridge-private`。
2. 可見性選 **Private**。
3. 建議先建立空倉庫，不要勾選自動新增 README、License 或 `.gitignore`。
4. 解壓專案 ZIP，把專案資料夾**裡面的所有檔案和資料夾**上傳到新倉庫的根目錄，再提交到預設分支（通常叫 `main`）。不要把整個專案資料夾再多套一層。
5. 確認 `.github/workflows/backup.yml` 與 `.github/workflows/publish.yml` 都已經提交到預設分支。

### 第 2 步：加入 Mataroa API Key

1. 登入 Mataroa，打開官方 API 文件：<https://mataroa.blog/api/docs/>，依文件取得你帳號的 API Key。
2. 在**私有 GitHub 倉庫**打開 **Settings → Secrets and variables → Actions**。
3. 按 **New repository secret**。
4. 名稱填 `MATAROA_API_KEY`，Secret 值填入 API Key，然後儲存。

**不要**把 API Key 寫在 README、Markdown、Python 或 YAML 檔案中，也不要貼到 Issue、聊天或提交記錄。如果密鑰曾經公開，請在 Mataroa 撤銷或更換，再更新 GitHub Secret。

### 第 3 步：手動執行首次備份

建議先從 Mataroa 匯出頁另外保存一份 Markdown ZIP：<https://mataroa.blog/export/>。這是額外備份，不是本工具運作的必要步驟。

1. 在私有倉庫打開 **Actions**。
2. 選 **Mataroa - Daily Backup**。
3. 點 **Run workflow**，選預設分支，再啟動工作流。
4. 完成後查看執行記錄，確認備份文章數量；並在 `posts/` 抽查標題、正文與中文內容。

之後工作流會依照每日 **UTC 20:17** 排程執行，即中國標準時間約**次日 04:17**。GitHub 定時工作流不保證在設定分鐘的當下準時啟動；也可以隨時在 Actions 頁面手動備份。

## 如何寫作及發布文章

### 第 1 步：在 `drafts/` 建立草稿

在私有倉庫的 `drafts/` 資料夾中，選 **Add file → Create new file**。檔名建議包含日期，例如 `2026-10-28-my-note.md`。

把以下內容貼入檔案，再修改標題、日期和正文：

```markdown
---
title: 文章標題
published_at: 2026-10-28
---

正文從這裡開始。

可以正常使用 Markdown 標題、連結和清單。
```

格式規則：

- 檔案必須以 `---` 開始，並以另一行 `---` 結束前置資料區塊。
- `title` 必填，而且不能是空白。
- `published_at` 可填 `YYYY-MM-DD` 格式的日期；不填或留空時，程式會使用中國標準時間的當日日期。
- `---` 之後是正文，不能留成全空白。
- 一個草稿只代表一篇新文章。**不要自行加入 `slug` 或 `url` 欄位**；本版本不透過 GitHub 修改已有文章。
- 編輯後按 **Commit changes**，把草稿提交到預設分支。只儲存草稿不會發布文章。

### 第 2 步：手動啟動發布

1. 打開私有倉庫的 **Actions**。
2. 選 **Mataroa - Publish Draft**。
3. 點 **Run workflow**。
4. 在 `draft_path` 輸入相對於倉庫根目錄的檔案路徑，例如 `drafts/2026-10-28-my-note.md`。
5. 確認選取的是包含該草稿的分支，再點一次 **Run workflow**。
6. 查看執行記錄。成功時會顯示文章標題、Mataroa URL 以及 GitHub 保存位置。

成功發布後，程式會把草稿移到 `published/`。之後每日備份會從 Mataroa 取得線上文章並存到 `posts/`。兩個資料夾可能包含同一篇文章，但用途不同：`published/` 留存由草稿發布的副本，`posts/` 則反映 Mataroa API 回傳的版本。

> [!CAUTION]
> 如果發布工作流中途失敗，先檢查 Mataroa 部落格是否已出現該文章，再決定是否重新執行。不要直接複製同一篇草稿並當作新文章發布。程式使用隱藏的 HTML 註解標記來協助識別已建立的文章；請勿手動刪除正文末尾的 `mataroa-bridge-id` 註解。

## 公開倉庫的安全設定

當你把本專案放到公開 GitHub 倉庫時：

1. 不要上傳真實的 `posts/`、`drafts/` 或 `published/` 內容；這個原始碼包中的這些資料夾是空的，只保留 `.gitkeep`。
2. 不要在公開倉庫設定 `MATAROA_API_KEY`，也不要用你的真實帳號執行工作流。
3. 打開 **Actions**，分別進入 **Mataroa - Daily Backup** 和 **Mataroa - Publish Draft** 工作流，使用工作流選單停用它們。這可避免公開原始碼展示倉庫因定時排程而持續執行失敗的工作。
4. 真正使用時，請用本專案檔案建立另一個私有倉庫，並只在私有倉庫設定 API Key。

如果文章或密鑰曾經被提交到公開倉庫，僅刪除檔案並不能清除 Git 歷史中所有副本；應依照 GitHub 的敏感資料移除指引處理，並立即輪換密鑰。

## 常見問題

**找不到 `Run workflow`？**

確認對應的 `.yml` 工作流已經提交到預設分支，並且目前檢視的是正確工作流。

**顯示缺少 `MATAROA_API_KEY`？**

確認你是在私有的實際使用倉庫中加入 Secret，名稱必須完全是 `MATAROA_API_KEY`。不要把密鑰貼到日誌或程式碼中。

**收到 HTTP 401 或 403？**

檢查 API Key 是否正確，以及是否加入到正在執行工作流的同一個倉庫。必要時在 Mataroa 更新密鑰，再更新 GitHub Secret。

**顯示 `Draft not found`？**

先確認草稿已提交到你選取的分支。`draft_path` 必須是從倉庫根目錄起算的路徑，例如 `drafts/my-note.md`，且檔案必須在 `drafts/` 內。

**發布後不確定有沒有成功？**

先檢查 Mataroa 上是否已有文章，再看 Actions 日誌。若請求結果不確定，程式會嘗試用穩定標記找回已建立的文章，避免盲目重複建立；仍應先檢查線上部落格。

**為什麼同一篇文章同時在 `posts/` 和 `published/`？**

這是刻意設計：`posts/` 是 Mataroa 現有內容的備份，`published/` 是透過草稿發布後留下的副本。它們不是兩篇線上文章，也不會因為有兩份本地檔案就建立兩篇 Mataroa 文章。

## 執行單元測試

本專案的測試不需要真實 Mataroa 帳號或 API Key。需要 Python 3.11 或更新版本：

```bash
python -m unittest discover -s tests -v
```

本專案沒有第三方 Python 套件相依性。

## 官方參考

- [Mataroa API 文件](https://mataroa.blog/api/docs/)
- [Mataroa Markdown 匯出](https://mataroa.blog/export/)
- [GitHub：手動執行工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [GitHub：設定倉庫可見性](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [GitHub：從倉庫移除敏感資料](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

## 授權條款

本專案以 MIT License 授權，詳見 [`LICENSE`](LICENSE)。
