# AI 跑团平台 - DnD 5e

基于 DnD 5e 规则的 AI 单人跑团平台。上传模组，创建角色，AI 担任 DM 和队友。

## 快速启动

### 1. 配置 Dify

将 `dify_workflows/` 目录下的 4 个 DSL 文件导入 Dify：

| 文件 | Workflow 名称 |
|------|-------------|
| `01_module_parser.yml` | 模组解析器 |
| `02_party_generator.yml` | 队伍生成器 |
| `03_game_master.yml` | 地下城主 |
| `04_combat_narrator.yml` | 战斗叙述器 |

### 2. 配置后端环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入 Dify 各 Workflow 的 API Key
```

`.env` 示例：
```
DIFY_BASE_URL=http://你的Dify地址/v1
DIFY_MODULE_PARSER_KEY=app-xxxx
DIFY_PARTY_GENERATOR_KEY=app-xxxx
DIFY_GAME_MASTER_KEY=app-xxxx
DIFY_COMBAT_NARRATOR_KEY=app-xxxx
```

### 3. 启动

**Windows 双击运行：**
```
start.bat
```

**手动启动：**
```bash
# 终端 1 - 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 终端 2 - 前端
cd frontend
npm install
npm run dev
```

访问 **http://localhost:3000**

## 使用流程

1. **上传模组** → 支持 PDF / DOCX / Markdown / TXT
2. **等待解析** → AI 自动提取模组信息（约 30-60 秒）
3. **创建角色** → 选择种族/职业/等级，分配能力值
4. **生成队伍** → AI 自动生成平衡的队友
5. **开始冒险** → 输入行动，AI DM 推进剧情

## 项目结构

```
ai-trpg/
├── backend/          # FastAPI 后端
│   ├── api/          # 路由层
│   ├── services/     # Dify客户端、规则引擎、文件解析
│   ├── models/       # 数据库模型
│   └── main.py
├── frontend/         # React 前端
│   └── src/
│       ├── pages/    # Home / CharacterCreate / Adventure
│       ├── store/    # Zustand 全局状态
│       └── api/      # API 调用封装
└── dify_workflows/   # 可直接导入的 Dify DSL 文件
```

## 技术栈

- **前端**: React + Vite + Tailwind CSS + Zustand
- **后端**: Python FastAPI + SQLite
- **AI编排**: Dify Workflow
- **文件解析**: PyMuPDF + python-docx
