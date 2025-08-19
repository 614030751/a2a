# 智能Agent搜索与验证服务

这是一个集成了**智能搜索**和**VC凭证验证**的一体化智能服务。它通过一个顺序工作流，帮助用户快速、可靠地从海量服务中找到经过可信验证的Agent。

## ✨ 核心工作流

本服务采用Google ADK的`SequentialAgent`进行编排，严格按照以下顺序执行任务：

1.  **第一步: 智能路由 (`RouterAgent`)**
    -   接收用户的自然语言搜索请求（例如 "我需要电池供应商"）。
    -   实时调用平台API，获取所有可用的Agent列表。
    -   利用大型语言模型（LLM）进行语义分析，从列表中初步筛选出与用户需求相关的Agent。
    -   将筛选出的Agent列表（包含`vcContent`等信息）传递给下一步。

2.  **第二步: VC凭证验证 (`VcVerifierAgent`)**
    -   接收上一步筛选出的Agent列表。
    -   自动遍历列表，提取每个Agent的`vcContent`。
    -   为每个`vcContent`调用指定的VC验证API。
    -   只保留那些通过了API验证的Agent。

3.  **最终输出**
    -   服务最终返回一个**已通过可信验证**的供应商列表。
    -   列表中每个供应商都包含名称、描述、URL、DID以及成功验证后的凭证ID等核心信息。

这个一体化流程确保了返回给用户的每一个结果都是相关且可信的。

## 🚀 快速开始

### 1. 环境设置

本项目使用 [Poetry](https://python-poetry.org/) 进行依赖管理。

首先，请确保您已经安装了 Poetry。然后，在项目根目录 (`search_agent/`) 下运行以下命令来创建虚拟环境并安装所有依赖：

```bash
poetry install
```

### 2. 启动服务

安装完依赖后，您可以通过以下命令启动FastAPI服务。服务将在 `http://localhost:8001` 上运行。

```bash
poetry run python -m search_agent
```

或者，如果您已经激活了Poetry的虚拟环境 (`poetry shell`)，可以直接运行：

```bash
python -m search_agent
```

### 3. 运行测试客户端

服务启动后，打开**另一个**终端窗口，并进入 `search_agent/` 目录。然后运行我们为您准备的测试客户端：

```bash
poetry run python test_client.py
```

或者在激活的虚拟环境中：

```bash
python test_client.py
```

您将在终端看到整个工作流的实时更新：
- 首先，`router` Agent会汇报它初步找到了哪些相关的供应商。
- 接着，`verifier` Agent会开始工作，并逐一汇报每个供应商的验证结果（成功或失败）。
- 最后，客户端会以格式化的JSON打印出**最终通过了所有验证的供应商列表**。
