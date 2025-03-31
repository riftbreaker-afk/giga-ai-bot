# Giga-AIbot

一个强大的游戏自动化机器人，支持多账号管理和智能游戏策略。

## 功能特点

- 🌟 多账号并发处理
- 🔄 智能重试机制
- 🌐 支持代理和直连网络
- 📝 详细的日志记录
- ⚡ 高性能并发处理

## 系统要求

- Python 3.8+
- 操作系统：Windows/Linux/MacOS
- 稳定的网络连接
- 足够的系统内存（建议 4GB+）

## 安装步骤

1. 克隆仓库：
```bash
# 方法1：使用命令行
git clone https://github.com/yourusername/Giga-AIbot.git

# 方法2：使用 GitHub Desktop
# 1. 打开 GitHub Desktop
# 2. 点击 "File" -> "Clone Repository"
# 3. 选择 "Giga-AIbot" 仓库
# 4. 注意：GitHub Desktop 可能会使用仓库的默认分支名称作为本地文件夹名称
# 5. 选择保存位置并点击 "Clone"
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境：
   - 复制 `config.yaml.example` 为 `config.yaml`
   - 根据需要修改配置文件

## 目录结构

```
项目根目录/
├── src/
│   ├── model/          # 游戏核心逻辑
│   ├── utils/          # 工具函数
│   └── constants.py    # 常量定义
├── data/               # 数据文件
├── logs/               # 日志文件
├── config.yaml         # 配置文件
├── main.py            # 主程序入口
└── process.py         # 账号处理逻辑
```

## 配置说明

在 `config.yaml` 中可以配置以下参数：

- `THREADS`: 并发处理线程数
- `ACCOUNTS_RANGE`: 账号处理范围
- `EXACT_ACCOUNTS_TO_USE`: 指定要使用的账号
- `SHUFFLE_ACCOUNTS`: 是否随机打乱账号顺序
- `ATTEMPTS`: 操作重试次数
- `PAUSE_BETWEEN_ATTEMPTS`: 重试间隔时间
- `RANDOM_INITIALIZATION_PAUSE`: 初始化延迟时间
- `GAME_SETTINGS`: 游戏相关配置
  - `TASK_INTERVAL`: 任务间隔时间
  - `MAX_RETRIES`: 最大重试次数
  - `ERROR_DELAY`: 错误延迟时间
- `DEEPSEEK_API`: DeepSeek API 配置（可选）
  - `API_KEY`: DeepSeek API 密钥
  - `MODEL`: 使用的模型名称
  - `TEMPERATURE`: 温度参数
  - 注意：不配置 DeepSeek API 时，系统将使用默认逻辑，可能导致操作失败率较高

## 使用方法

1. 准备账号数据：
   - 在 `data/account.csv` 中添加账号信息
   - 格式：`GIGA_TOKEN,PROXY(可选)`
   - ⚠️ 重要说明：
     - Token 有效期为 24 小时
     - 每天需要重新获取并更新 Token
     - 过期 Token 将无法使用，程序会报错
     - 建议每天程序启动前更新 account.csv 中的 Token
   - 代理配置说明：
     - 代理是可选的，不配置代理时系统会自动使用直连网络
     - 配置代理可以提高账号安全性和稳定性
   - 代理格式示例：
     ```
     GIGA_TOKEN,PROXY
     token1,http://username:password@ip:port    # 使用代理
     token2,                                    # 不配置代理，使用直连
     token3,socks5://ip:port                   # 使用代理
     ```
   - 支持的代理协议：
     - HTTP: `http://ip:port` 或 `http://username:password@ip:port`
     - HTTPS: `https://ip:port` 或 `https://username:password@ip:port`
     - SOCKS5: `socks5://ip:port` 或 `socks5://username:password@ip:port`
   - 注意事项：
     - 代理地址必须包含协议前缀（http://、https://、socks5://）
     - 如果代理需要认证，请使用 `username:password@` 格式
     - 端口号必须正确填写
     - 不配置代理时留空即可，系统会自动使用直连网络

2. 运行程序：
```bash
python main.py
```

3. 选择操作：
   - 根据菜单提示选择要执行的操作
   - 程序会自动处理指定范围内的账号
   - 重要提示：
     - 程序运行期间，游戏画面不会显示，但会持续消耗体力
     - 请及时关注体力消耗情况，避免体力耗尽
     - 如需停止程序，请使用 Ctrl+C 安全退出
     - 建议设置合理的操作间隔，避免体力快速消耗
     - 每天首次运行前请确保更新了最新的 Token

## 日志系统

- 日志文件保存在 `logs/` 目录
- 包含详细的执行记录和错误信息
- 支持实时监控系统性能
- 记录游戏操作日志
- 错误追踪和调试信息

## 错误处理

- 自动重试机制
- 错误日志记录
- 优雅的异常处理
- 游戏状态恢复
- 网络异常处理

## 注意事项

1. 请确保账号数据的安全性
2. 建议使用代理以提高稳定性
3. 合理设置并发数和延迟时间
4. 定期检查日志文件
5. 遵守游戏规则和条款
6. 避免频繁操作导致账号风险
7. 建议使用稳定的网络环境
8. ⚠️ 每天更新 Token，避免使用过期 Token
9. 运行前检查 Token 有效性

## 常见问题

1. Q: Token 无法使用怎么办？
   A: Token 有效期为 24 小时，请确保使用最新的 Token。每天需要重新获取并更新 account.csv 文件。

2. Q: 如何设置代理？
   A: 在 account.csv 文件中添加代理地址即可。

3. Q: 支持哪些游戏操作？
   A: 支持自动登录、任务执行、资源收集等基础操作。

4. Q: 如何避免账号风险？
   A: 建议设置合理的操作间隔，避免频繁操作。

5. Q: 程序报错显示 Token 无效？
   A: 请检查：
      - Token 是否已过期（超过24小时）
      - Token 格式是否正确
      - 是否使用了最新的 Token
      - 建议重新获取 Token 并更新配置文件

## 免责声明

本工具仅供学习和研究使用，请遵守游戏规则和相关法律法规。使用本工具产生的任何后果由使用者自行承担。