# Mataroa × GitHub Bridge

**Back up your [Mataroa](https://mataroa.blog/) blog to GitHub, write drafts in Markdown, and publish new posts to Mataroa with GitHub Actions.**

[繁體中文](README.zh-TW.md)

This project uses Python's standard library and GitHub Actions. No third-party Python packages or personal server are required.

> [!IMPORTANT]
> **Use a private repository for your actual blog backup and publishing workflows.**
>
> The backup workflow commits your blog posts to the repository where it runs. If that repository is public, your private articles could become public. Never put real blog content or your `MATAROA_API_KEY` in a public repository. Keep the public repository for sharing source code only.

## Features

- **Automatic backups:** Fetch posts from Mataroa and save them as Markdown files in `posts/`.
- **Write anywhere:** Create and edit Markdown drafts in `drafts/`, including through the GitHub mobile app.
- **Manual publishing:** Publish a draft to Mataroa by manually running a GitHub Actions workflow.
- **Version history:** Git records changes to backed-up posts and project files.
- **Duplicate-publishing safeguards:** The tool assigns a stable identifier to a draft and checks Mataroa before publishing, helping recover from certain interrupted or uncertain publishing attempts.

## What This Project Does Not Do

- It currently supports **publishing new posts only**. To edit an existing post, edit it directly on Mataroa. A subsequent backup will update its copy in `posts/`.
- It backs up posts returned by the Mataroa API, not custom pages or comments.
- Image URLs in your posts are preserved, but the image files themselves are not downloaded and backed up.
- A post missing from a later API response is not automatically deleted from `posts/`.
- This tool is not a replacement for keeping an independent backup.

## Repository Structure

| Path | Purpose |
|---|---|
| `posts/` | Markdown copies of posts fetched from Mataroa. |
| `drafts/` | New posts waiting to be published. |
| `published/` | Copies of drafts successfully published through this tool. |
| `scripts/mataroa_sync.py` | Main program for backup, draft validation, and publishing. |
| `.github/workflows/backup.yml` | Scheduled and manually triggered backup workflow. |
| `.github/workflows/publish.yml` | Manually triggered publishing workflow. |
| `tests/` | Unit tests that do not require a Mataroa account. |

A post may appear in both `posts/` and `published/`. This is intentional: `posts/` reflects the version fetched from Mataroa, while `published/` preserves the draft used for publishing. These local copies do not create duplicate online posts.

---

## Setup Guide

### 1. Create a Private GitHub Repository

Create a new repository on [GitHub](https://github.com/) and set its visibility to **Private**. For example:

`mataroa-github-bridge-private`

Then:

1. Download and extract this project.
2. Upload the **contents of the project folder** to the root of your new repository. Do not add another nested project folder.
3. Commit the files to your default branch, usually `main`.
4. Confirm that both workflow files are present:
   - `.github/workflows/backup.yml`
   - `.github/workflows/publish.yml`

The workflows must be committed to the repository's default branch for scheduled backups to run as expected.

### 2. Add Your Mataroa API Key

1. Sign in to Mataroa and open the [official API documentation](https://mataroa.blog/api/docs/) to obtain your API key.
2. In your **private GitHub repository**, go to **Settings → Secrets and variables → Actions**.
3. Select **New repository secret**.
4. Set the name to exactly `MATAROA_API_KEY`.
5. Paste your API key into the secret value and save it.

Never hard-code your API key in Python, YAML, Markdown, or other files. Do not commit it to Git or share it in issues or logs.

If your key has ever been exposed, revoke or replace it in Mataroa and update the GitHub secret.

### 3. Run Your First Backup

Before starting, consider making an independent backup using the [Mataroa Markdown export page](https://mataroa.blog/export/). This is an additional precaution, not a requirement for the tool to work.

To run the backup:

1. Open your private repository on GitHub.
2. Select **Actions**.
3. Choose **Mataroa - Daily Backup**.
4. Click **Run workflow** and select the default branch.
5. Start the workflow and wait for the run to finish.
6. Inspect `posts/` and check several articles to confirm that their titles, body text, and non-English characters are preserved.

The backup is scheduled for **20:17 UTC every day**, which is approximately **04:17 the following day in China Standard Time (UTC+8)**. GitHub Actions does not guarantee that scheduled workflows start at the exact scheduled minute. You can also run a backup manually at any time.

If no backup files have changed, the workflow does not create an unnecessary commit.

---

## Write and Publish a New Post

### 1. Create a Draft

In your private repository, open the `drafts/` directory and select **Add file → Create new file**.

Use a descriptive filename, such as:

`drafts/2026-10-28-my-note.md`

Start with this template:

```markdown
---
title: My New Post
published_at: 2026-10-28
---

Write your article here.

You can use normal Markdown syntax, including headings, links, and lists.
```

**Draft formatting rules:**

- The file must begin with a `---` line, followed by the metadata and another `---` line.
- `title` is required and must not be empty.
- `published_at` is optional. If provided, use the `YYYY-MM-DD` date format. If omitted or left empty, the tool uses the current date in China Standard Time.
- The body after the metadata must not be empty.
- Do not add your own `slug` or `url` fields. This version is for publishing new posts, not editing existing ones.
- Commit the draft to the branch you intend to publish from. Saving an uncommitted draft does not publish it.

You can write and commit drafts using the GitHub website or mobile app.

### 2. Publish the Draft Manually

1. Open your private repository and select **Actions**.
2. Choose **Mataroa - Publish Draft**.
3. Click **Run workflow**.
4. In `draft_path`, enter the path relative to the repository root. For example:

   `drafts/2026-10-28-my-note.md`

5. Make sure the selected branch contains the committed draft.
6. Start the workflow and inspect its run log.

After a successful publication, the workflow moves the draft to `published/`. The daily backup later retrieves the online post from Mataroa and saves it to `posts/`.

> [!CAUTION]
> If a publishing workflow fails or is interrupted, check your Mataroa blog before trying again. The post may already have been created even if the workflow did not finish. Do not publish a duplicate draft blindly.
>
> The tool uses a stable identifier stored in the draft and an HTML comment marker to help recognize an article that has already been created. Do not manually remove the `mataroa-bridge-id` comment at the end of a published post's body.

---

## Keep the Public Repository Safe

If you want to open-source this project, maintain two separate repositories:

- **Public repository:** Source code, documentation, tests, and license.
- **Private repository:** Your real blog backups, drafts, publishing history, and API key.

For the public repository:

1. Do not commit real content to `posts/`, `drafts/`, or `published/`. The directories in this source package are empty placeholders.
2. Do not add your real `MATAROA_API_KEY`.
3. Do not run the backup or publishing workflows against your real Mataroa account.
4. In the public repository's **Actions** page, disable both **Mataroa - Daily Backup** and **Mataroa - Publish Draft**.
5. Use a separate private repository for actual operation.

Deleting a secret or article from the latest version of a repository does not necessarily remove it from Git history. If sensitive content has been committed publicly, follow GitHub's [guidance for removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). Rotate any exposed API key immediately.

---

## Troubleshooting

### “Run workflow” is not available

Check that the workflow file is committed to the repository's default branch and that you have opened the correct workflow.

### The workflow reports a missing `MATAROA_API_KEY`

Make sure the secret is configured in the same repository where the workflow is running. Its name must be exactly `MATAROA_API_KEY`.

### The request returns HTTP 401 or 403

Check that the API key is valid and that the secret is configured correctly. If necessary, replace the key in Mataroa and update the GitHub secret.

### The workflow reports “Draft not found”

Confirm that the draft has been committed to the selected branch and that `draft_path` is correct. For example:

`drafts/my-note.md`

The draft must be inside the `drafts/` directory.

### You are unsure whether publishing succeeded

Check your live Mataroa blog first, then inspect the workflow log. When the result of a publishing request is uncertain, the tool attempts to identify an already-created post using its stable marker. Always verify the online result before retrying.

### Why are there copies of the same article in two folders?

This is expected. `posts/` contains the version fetched from Mataroa; `published/` contains the draft copy saved after publishing. The two local files serve different purposes and do not mean that two online posts were created.

---

## Run the Tests

The unit tests do not need a Mataroa account or API key. Use Python 3.11 or newer:

```bash
python -m unittest discover -s tests -v
```

The project has no third-party Python package dependencies.

## References

- [Mataroa API documentation](https://mataroa.blog/api/docs/)
- [Mataroa Markdown export](https://mataroa.blog/export/)
- [GitHub: Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [GitHub: Setting repository visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details.
