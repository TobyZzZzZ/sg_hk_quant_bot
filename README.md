# Roostoo 量化交易机器人

这是一个基于 Python 的模块化量化交易框架，支持实盘交易与历史回测。经过重构，实现了策略逻辑与回测引擎的完全解耦。

## 架构特点

- **解耦设计**：策略代码与回测框架分离，所有策略必须继承 `BaseStrategy` 接口。
- **动态加载**：使用工厂模式动态加载策略，无需修改框架代码即可新增策略。
- **纯粹回测引擎**：`src/backtest` 仅包含核心回测组件（数据加载、订单执行、账户追踪、绩效分析）。
- **统一入口**：提供 `backtest_runner.py`（回测）和 `live_trading.py`（实盘）两个统一入口。

## 项目结构

```text
sg_hk_quant_bot/
├── src/
│   ├── api/            # API 客户端 (如 Roostoo 等)
│   ├── interfaces/     # 核心接口定义 (BaseStrategy 等)
│   ├── strategies/     # 纯策略仓库 (双均线、多因子、网格等)
│   ├── backtest/       # 纯回测引擎 (引擎、账户、执行、数据馈送、分析)
│   └── utils/          # 通用工具函数
├── backtest_runner.py  # 统一回测入口
├── live_trading.py     # 统一实盘入口
├── config.py           # 配置 (如需)
├── pyproject.toml      # 项目依赖管理 (uv)
└── data/               # 历史数据存放目录
```

## 快速开始

### 1. 配置 API 密钥 (针对实盘)

如需实盘交易，创建 `config.py`（如果使用了依赖 API 的策略）并填入相关密钥。

### 2. 运行回测
使用统一的回测运行器，通过命令行参数指定策略和数据源：

```bash
# 运行双均线策略回测
uv run python backtest_runner.py --strategy dualma --data data/YOUR_DATA.csv

# 运行网格策略回测
uv run python backtest_runner.py --strategy grid --data data/YOUR_DATA.csv
```

**查看回测结果**：
回测完成后，程序会在控制台打印核心绩效指标（如总收益率、最大回撤、交易次数等）。此外，详细的资金曲线和交易记录会被导出到 `reports/` 目录下：
- `reports/equity_curve.csv`: 资金净值变化曲线
- `reports/trades.csv`: 详细的每笔交易记录

### 3. 运行实盘 (Mock API)

使用统一的实盘运行器启动策略：

```bash
# 运行双均线策略实盘
uv run python live_trading.py --strategy dualma --symbol BTC/USDT --interval 60
```

## 如何添加新策略

1. 在 `src/strategies/` 目录下创建新的策略文件。
2. 确保策略类继承自 `src.interfaces.strategy.BaseStrategy`。
3. 实现 `initialize()`, `handle_data()` 和 `analyze()` 方法。
4. 在 `backtest_runner.py` 和 `live_trading.py` 的 `STRATEGIES` 字典中注册你的策略类。

## 依赖管理

本项目推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖：

```bash
uv sync
```

