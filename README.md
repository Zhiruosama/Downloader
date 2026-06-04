# Downloader

一个自用为主的多平台下载器。前端使用 Tauri + React,后端使用 Python + FastAPI + yt-dlp。

## 当前功能

- 多链接批量加入下载队列
- 支持 yt-dlp 覆盖的平台,如 YouTube、Bilibili、Twitter、TikTok 等
- 清晰度/格式选择
- 下载进度、任务状态、历史记录
- 默认保存路径、默认画质、命名模板、并发数配置
- cookies.txt 高级备用方案

## 开发环境

需要安装:

- Python 3.13+
- Node.js 22+
- Rust / Cargo
- FFmpeg

安装 Python 依赖:

```powershell
pip install -r requirements.txt
```

安装前端依赖:

```powershell
cd desktop
npm install
```

## 启动开发版

推荐使用一键脚本:

```powershell
.\start-dev.ps1
```

手动启动:

```powershell
python main.py
```

另开一个终端:

```powershell
cd desktop
npm run tauri:dev
```

## 常用验证

后端编译检查:

```powershell
python -m py_compile app/server.py app/core/queue_service.py app/core/downloader.py
```

前端检查:

```powershell
cd desktop
npm run lint
npm run build
```

## 目录结构

```text
app/
  core/        下载核心、队列、配置、历史记录
  models/      任务模型
  server.py    本地 API 服务
desktop/       Tauri + React GUI 客户端
main.py        后端入口
start-dev.ps1  开发版一键启动脚本
```

## 说明

开发阶段会同时启动 Python 后端和 Tauri GUI。最终打包时计划将后端作为后台进程随桌面客户端启动,避免用户看到终端窗口。
