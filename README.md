# Roostoo 量化交易机器人

这是一个基于 Roostoo Mock API 的量化交易机器人框架。

## 项目结构

```text
sg_hk_quant_bot/
├── src/
│   ├── api/            # API 客户端 (Roostoo)
│   ├── data/           # 数据获取与处理
│   ├── strategies/     # 交易策略逻辑
│   ├── backtest/       # 回测引擎与优化器
│   └── utils/          # 通用工具函数
├── main.py             # 实盘交易入口
├── run_backtest.py     # 回测与参数优化入口
├── config.py           # API 密钥配置 (需本地创建)
├── symbols.json        # 监控币种列表
└── pyproject.toml      # 项目依赖管理 (uv)
```

## 快速开始

### 1. 配置 API 密钥
创建 `config.py` 并填入你的 Roostoo API 密钥：
```python
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
```

### 2. 运行策略
使用默认的多因子策略：
```bash
python main.py --strategy multi_factor
```
使用入门的双均线策略：
```bash
python main.py --strategy toy
```

### 3. 运行回测
```bash
# 单次回测
python run_backtest.py --mode run --interval 1h

# 参数优化
python run_backtest.py --mode optimize
```

## 依赖管理
本项目推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖：
```bash
uv sync
uv run python main.py
```
