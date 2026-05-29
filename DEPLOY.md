# NarrativeLoom 网页部署指南

本项目是 **Streamlit** 应用，推荐使用 [Streamlit Community Cloud](https://share.streamlit.io/) 免费部署（与 GitHub 联动）。

## 一、Streamlit Cloud（推荐）

### 1. 推送代码到 GitHub

确保仓库 `https://github.com/Gxy-an/AIPractice-Narrativeloom` 已包含最新代码（`app.py`、`requirements.txt` 等）。

### 2. 登录并创建应用

1. 打开 [share.streamlit.io](https://share.streamlit.io/)，用 GitHub 登录  
2. 点击 **New app**  
3. 选择仓库 `Gxy-an/AIPractice-Narrativeloom`  
4. **Main file path** 填：`app.py`  
5. **Branch** 选：`main`  

### 3. 配置 Secrets（API 密钥）

在应用 **Settings → Secrets** 中粘贴（勿泄露真实密钥到公开仓库）：

```toml
MIMO_API_KEY = "你的密钥"
OPENAI_API_KEY = "你的密钥"
OPENAI_BASE_URL = "https://api.xiaomimimo.com/v1"
LLM_MODEL = "mimo-v2-flash"
```

也可参考仓库内 `.streamlit/secrets.toml.example`。

### 4. 部署

保存后 Cloud 会自动构建并给出公网 URL，形如：  
`https://aipractice-narrativeloom-xxxx.streamlit.app`

---

## 二、本地预览（部署前自测）

```powershell
cd D:\AIPractice\AIPractice-Narrativeloom
.\install.ps1
# 配置 .env（复制 .env.example 并填入密钥）
py -3 -m streamlit run app.py
```

浏览器访问 `http://localhost:8501`。

---

## 三、其它平台（Render / Railway / VPS）

启动命令统一为：

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

将 `MIMO_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL` 等设为平台环境变量即可。

---

## 注意事项

- **切勿**将 `.env` 或 `.streamlit/secrets.toml` 提交到 Git  
- 云端无持久磁盘时，草稿 JSON 可能在重启后丢失；正式使用可考虑挂载存储或数据库  
- 若构建超时，可在 `requirements.txt` 中去掉未使用的依赖以加快安装
