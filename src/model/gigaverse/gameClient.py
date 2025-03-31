import asyncio
import logging
import random
from aiohttp import ClientSession
from typing import Tuple, Optional
from src.model.deepseek.deepseek import ask_deepseek
from src.utils.constants import Account
from curl_cffi.requests import AsyncSession

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DeepSeek配置
class Config:
    class DEEPSEEK:
        API_KEYS = ["sk-2ab59adf27834069a2fa688f91446998"]  # 已提供
        MODEL = "deepseek-chat"
        PROXY_FOR_DEEPSEEK = None

# 优化的REFERENCED_MESSAGES_SYSTEM_PROMPT
REFERENCED_MESSAGES_SYSTEM_PROMPT = """
你是一个智能游戏助手，帮助玩家在基于“石头、布、剪刀”规则的dungeon游戏中选择最佳出招和战利品。请严格按照以下规则和逻辑进行分析，并返回指定格式的纯文本建议。

### 出招规则：
1. **技能使用与恢复**：
   - 每个招式（rock、paper、scissor）有`currentCharges`表示可用次数。
   - 当`currentCharges`为1时，强制不使用该招式，因使用后会变为-1，需两回合恢复至1，必须选择其他`currentCharges` > 1的招式。
   - 当`currentCharges`为-1时，该招式不可用，禁止选择。
   - 只从`currentCharges` > 1的招式中选择，确保下一回合仍有可用选项。
2. **目标**：
   - 根据玩家和敌人的血量（health）、护盾（shield）、招式属性（ATK和DEF），选择能最大化伤害或保护自己的招式。
   - 若敌人血量低，优先高ATK招式（仅限`currentCharges` > 1）；若玩家血量低，优先高DEF招式（仅限`currentCharges` > 1）。

### 战利品选择规则：
1. **稀有度与实用性**：
   - `RARITY_CID`表示战利品稀有程度，数值越高越珍贵，应优先考虑。
   - 但需结合当前状态评估实用性：
     - 若玩家满血（health接近最大值），避免选择恢复血量的战利品（如'AddMaxHealth'），即使稀有度高。
     - 若玩家招式属性弱（如ATK或DEF低），优先选择增强招式的战利品（如'UpgradeRock'）。
     - 若护盾低，考虑增加护盾的战利品（如'AddMaxArmor'）。
2. **目标**：
   - 在稀有度和实用性间平衡，选择对当前战斗最有利的战利品。

### 返回格式：
- 出招建议：`建议出<选择>，因为<理由>`
  - 示例：`建议出paper，因为生存性高且Charges > 1，石头Charges为1不可用`
- 战利品建议：`建议出<选择>，因为<理由>`
  - 示例：`建议出loot_three，因为稀有度高且增加生命值`

请根据输入的状态和选项进行分析，确保建议符合上述规则。特别注意：强制不使用`currentCharges`为1的招式，只从`currentCharges` > 1的招式中选择。
"""

class GameClient:
    def __init__(self,
            account: Account,
            client: AsyncSession,
            config: Config):
        self.account = account
        self.client = client
        self.config = config
        self.current_action_token = ""
        self.player = {
            "health": None,
            "shield": None,
            "max_health": None,
            "moves": {
                "rock": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0},
                "paper": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0},
                "scissor": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0}
            }
        }
        self.enemy = {
            "health": None,
            "shield": None,
            "moves": {
                "rock": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0},
                "paper": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0},
                "scissor": {"currentATK": 0, "currentDEF": 0, "currentCharges": 0}
            }
        }
        self.loot_options = []
        self.last_enemy_move = None
        self.result_json = None

    async def _deepseek_referenced_messages(self, main_message_content: str, referenced_message_content: str) -> str:
        """使用DeepSeek生成回复，若失败返回空字符串"""
        try:
            api_key = random.choice(self.config.DEEPSEEK.API_KEYS)
            user_message = f"消息1: {referenced_message_content}\n消息2: {main_message_content}"
            success, response = await ask_deepseek(
                api_key=api_key,
                model=self.config.DEEPSEEK.MODEL,
                user_message=user_message,
                prompt=REFERENCED_MESSAGES_SYSTEM_PROMPT,
                proxy=self.config.DEEPSEEK.PROXY_FOR_DEEPSEEK,
            )

            if not success:
                logger.warning(f"{self.account.index} | DeepSeek API失败: {response}")
                return ""
            return response
        except Exception as e:
            logger.warning(f"{self.account.index} | DeepSeek错误: {str(e)}")
            return ""

    async def send_game_action(
            self,
            action: str,
            action_token: str,
            dungeon_id: int = 0,
            consumables: list = None,
            item_id: int = 0,
            index: int = 0
    ) -> Tuple[bool, dict]:
        """发送游戏动作到API，失败时重试3次，3次失败后结束任务"""
        proxy = self.account.proxy
        if proxy and not proxy.startswith(("http://", "https://", "socks5://", "socks5h://")):
            proxy = f"http://{proxy}"
        masked_proxy = (
            f"{proxy.split('://')[0]}://[hidden]@{proxy.split('@')[-1]}" if proxy else "None") if proxy else "None"

        headers = {
            "accept": "*/*",
            "accept-language": "zh,zh-CN;q=0.9",
            "authorization": f"Bearer {self.account.token}",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "origin": "https://gigaverse.io",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://gigaverse.io/play",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }

        json_data = {
            "action": action,
            "actionToken": action_token,
            "dungeonId": dungeon_id,
            "data": {
                "consumables": consumables if consumables is not None else [],
                "itemId": item_id,
                "index": index
            }
        }

        max_retries = 5
        retry_delay = 3  # 每次重试等待2秒

        for attempt in range(max_retries):
            try:
                async with ClientSession() as client:
                    logger.info(headers)
                    logger.info(json_data)
                    logger.info(
                        f"{self.account.index} | 发送动作: {action} (token: {action_token}, proxy: {masked_proxy}, 尝试次数: {attempt + 1}/{max_retries})")
                    response = await client.post(
                        "https://gigaverse.io/api/game/dungeon/action",
                        headers=headers,
                        json=json_data,
                        proxy= None  # 使用proxy参数而不是None
                    )
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"{self.account.index} | 动作失败: {response.status} - {error_text}")
                        if attempt < max_retries - 1:
                            logger.info(f"{self.account.index} | 将在 {retry_delay} 秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                        raise RuntimeError(f"动作 {action} 在 {max_retries} 次尝试后失败，终止任务")

                    result = await response.json()
                    logger.info(f"{self.account.index} | 动作成功: {action}")
                    return True, result

            except Exception as e:
                logger.error(f"{self.account.index} | 发送动作异常: {str(e)} (尝试次数: {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.info(f"{self.account.index} | 将在 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue
                logger.error(f"{self.account.index} | 动作 {action} 在 {max_retries} 次尝试后仍然失败，终止任务")
                raise RuntimeError(f"动作 {action} 在 {max_retries} 次尝试后失败，终止任务") from e

        # 此行理论上不会执行，因为失败时会抛出异常，但保留以保持逻辑完整性
        logger.error(f"{self.account.index} | 动作 {action} 在 {max_retries} 次尝试后仍然失败")
        return False, {}

    def update_status(self, result: dict):
        """从返回结果更新状态，直接使用lastMove获取敌方动作"""
        players = result["data"]["run"]["players"]
        player, enemy = players[0], players[1]


        self.player.update({
            "health": player["health"]["current"],
            "shield": player["shield"]["current"],
            "max_health": player["health"].get("currentMax", player["health"]["current"]),
            "moves": {
                "rock": {
                    "currentATK": player["rock"]["currentATK"],
                    "currentDEF": player["rock"]["currentDEF"],
                    "currentCharges": player["rock"]["currentCharges"]
                },
                "paper": {
                    "currentATK": player["paper"]["currentATK"],
                    "currentDEF": player["paper"]["currentDEF"],
                    "currentCharges": player["paper"]["currentCharges"]
                },
                "scissor": {
                    "currentATK": player["scissor"]["currentATK"],
                    "currentDEF": player["scissor"]["currentDEF"],
                    "currentCharges": player["scissor"]["currentCharges"]
                }
            }
        })
        self.enemy.update({
            "health": enemy["health"]["current"],
            "shield": enemy["shield"]["current"],
            "moves": {
                "rock": {
                    "currentATK": enemy["rock"]["currentATK"],
                    "currentDEF": enemy["rock"]["currentDEF"],
                    "currentCharges": enemy["rock"]["currentCharges"]
                },
                "paper": {
                    "currentATK": enemy["paper"]["currentATK"],
                    "currentDEF": enemy["paper"]["currentDEF"],
                    "currentCharges": enemy["paper"]["currentCharges"]
                },
                "scissor": {
                    "currentATK": enemy["scissor"]["currentATK"],
                    "currentDEF": enemy["scissor"]["currentDEF"],
                    "currentCharges": enemy["scissor"]["currentCharges"]
                }
            }
        })
        self.current_action_token = str(result.get("actionToken", ""))
        self.loot_options = result["data"]["run"].get("lootOptions", [])
        self.last_enemy_move = enemy.get("lastMove", "未知")
        self.result_json = result

    async def analyze_next_move(self) -> str:
        """使用AI分析下一步出招，强制不使用Charges为1的招式"""
        available_moves = [m for m, data in self.player["moves"].items() if data["currentCharges"] > 1]  # 强制只选Charges > 1
        if not available_moves:
            logger.warning(f"{self.account.index} | 无Charges > 1的招式，检查Charges > 0的招式")
            available_moves = [m for m, data in self.player["moves"].items() if data["currentCharges"] > 0]
            if not available_moves:
                logger.warning(f"{self.account.index} | 无可用招式，默认选择rock")
                return "rock"

        state = (
            f"玩家: 血量={self.player['health']}/{self.player['max_health']}, 护盾={self.player['shield']}, "
            f"招式=[rock: ATK={self.player['moves']['rock']['currentATK']}, DEF={self.player['moves']['rock']['currentDEF']}, Charges={self.player['moves']['rock']['currentCharges']}, "
            f"paper: ATK={self.player['moves']['paper']['currentATK']}, DEF={self.player['moves']['paper']['currentDEF']}, Charges={self.player['moves']['paper']['currentCharges']}, "
            f"scissor: ATK={self.player['moves']['scissor']['currentATK']}, DEF={self.player['moves']['scissor']['currentDEF']}, Charges={self.player['moves']['scissor']['currentCharges']}]"
            f"\n敌人: 血量={self.enemy['health']}, 护盾={self.enemy['shield']}, "
            f"招式=[rock: ATK={self.enemy['moves']['rock']['currentATK']}, DEF={self.enemy['moves']['rock']['currentDEF']}, Charges={self.enemy['moves']['rock']['currentCharges']}, "
            f"paper: ATK={self.enemy['moves']['paper']['currentATK']}, DEF={self.enemy['moves']['paper']['currentDEF']}, Charges={self.enemy['moves']['paper']['currentCharges']}, "
            f"scissor: ATK={self.enemy['moves']['scissor']['currentATK']}, DEF={self.enemy['moves']['scissor']['currentDEF']}, Charges={self.enemy['moves']['scissor']['currentCharges']}]"
        )
        prompt = (
            "根据以下状态建议下一步出招（选项：rock、paper、scissor），并严格按照以下格式返回纯文本：\n"
            "建议出<选择>，因为<理由>\n"
            "其中 <选择> 必须是 rock、paper 或 scissor 中的一个，不含尖括号或其他标记。\n"
            "注意：强制不使用`currentCharges`为1的招式，只从`currentCharges` > 1的招式中选择。\n"
            "示例：建议出paper，因为生存性高且Charges > 1，rock Charges为1不可用\n\n"
        )

        ai_response = await self._deepseek_referenced_messages(prompt, state)
        logger.info(f"{self.account.index} | DeepSeek原始响应: {ai_response}")

        if ai_response:
            try:
                if "建议出" in ai_response:
                    suggestion_part = ai_response.split("建议出")[1]
                    suggestion = suggestion_part.split("，因为")[0].replace("*", "").strip()
                    reason = suggestion_part.split("，因为")[1].strip() if "，因为" in suggestion_part else "未提供理由"

                    if suggestion in available_moves:
                        logger.info(f"{self.account.index} | AI选择进攻: {suggestion}, 理由: {reason}")
                        return suggestion
                    else:
                        logger.warning(f"{self.account.index} | AI建议的招式 {suggestion} 不可用（可能是Charges=1或-1）")
                        return available_moves[0]  # 若AI建议不可用，选择第一个可用招式
                else:
                    for move in available_moves:
                        if move in ai_response.lower():
                            logger.info(f"{self.account.index} | AI模糊匹配到: {move}")
                            return move
                    logger.warning(f"{self.account.index} | AI响应中未找到有效招式")
            except Exception as e:
                logger.warning(f"{self.account.index} | AI建议解析失败，错误: {str(e)}, 响应: {ai_response}")

        # 默认策略
        total_life = self.player["health"] + self.player["shield"]
        enemy_total_life = self.enemy["health"] + self.enemy["shield"]
        if total_life <= 5 and "paper" in available_moves:
            logger.info(f"{self.account.index} | 血量危急，选择paper，剩余血量={total_life}")
            return "paper"
        if enemy_total_life <= 5 and "rock" in available_moves:
            logger.info(f"{self.account.index} | 敌人残血，选择rock，敌人剩余血量={enemy_total_life}")
            return "rock"
        move = available_moves[0]  # 从Charges > 1中选第一个
        logger.info(f"{self.account.index} | 默认选择: {move}")
        return move

    async def choose_loot(self) -> str:
        """使用AI选择战利品，考虑RARITY_CID和实用性"""
        if not self.loot_options:
            logger.warning(f"{self.account.index} | 无战利品选项，默认选择loot_three")
            return "loot_three"

        loot_details = (
            f"loot_one: {self.loot_options[0] if len(self.loot_options) > 0 else '无'}, "
            f"loot_two: {self.loot_options[1] if len(self.loot_options) > 1 else '无'}, "
            f"loot_three: {self.loot_options[2] if len(self.loot_options) > 2 else '无'}"
        )
        logger.info(f"{self.account.index} | 可选战利品 - {loot_details}")

        state = (
            f"玩家: 血量={self.player['health']}/{self.player['max_health']}, 护盾={self.player['shield']}, "
            f"招式=[rock: ATK={self.player['moves']['rock']['currentATK']}, DEF={self.player['moves']['rock']['currentDEF']}, Charges={self.player['moves']['rock']['currentCharges']}, "
            f"paper: ATK={self.player['moves']['paper']['currentATK']}, DEF={self.player['moves']['paper']['currentDEF']}, Charges={self.player['moves']['paper']['currentCharges']}, "
            f"scissor: ATK={self.player['moves']['scissor']['currentATK']}, DEF={self.player['moves']['scissor']['currentDEF']}, Charges={self.player['moves']['scissor']['currentCharges']}]"
            f"\n战利品选项: {loot_details}"
        )
        prompt = (
            "根据以下状态和战利品选项建议选择（选项：loot_one、loot_two、loot_three），并严格按照以下格式返回纯文本：\n"
            "建议出<选择>，因为<理由>\n"
            "其中 <选择> 必须是 loot_one、loot_two 或 loot_three 中的一个，不含尖括号或其他标记。\n"
            "示例：建议出loot_one，因为稀有度高且增加生命值\n\n"
        )

        ai_response = await self._deepseek_referenced_messages(prompt, state)
        logger.info(f"{self.account.index} | DeepSeek原始响应: {ai_response}")

        if ai_response:
            try:
                if "建议出" in ai_response:
                    suggestion_part = ai_response.split("建议出")[1]
                    suggestion = suggestion_part.split("，因为")[0].replace("<", "").replace(">", "").replace("*", "").strip()
                    reason = suggestion_part.split("，因为")[1].strip() if "，因为" in suggestion_part else "未提供理由"

                    valid_options = ["loot_one", "loot_two", "loot_three"]
                    if suggestion in valid_options:
                        logger.info(f"{self.account.index} | AI选择战利品: {suggestion}, 理由: {reason}")
                        return suggestion
                    else:
                        logger.warning(f"{self.account.index} | AI建议的战利品 {suggestion} 无效")
                else:
                    for option in ["loot_one", "loot_two", "loot_three"]:
                        if option in ai_response.lower():
                            logger.info(f"{self.account.index} | AI模糊匹配到: {option}")
                            return option
                    logger.warning(f"{self.account.index} | AI响应中未找到有效战利品选项")
            except Exception as e:
                logger.warning(f"{self.account.index} | AI战利品建议解析失败，错误: {str(e)}, 响应: {ai_response}")

        logger.info(f"{self.account.index} | 默认选择loot_three，选项: {loot_details}")
        return "loot_three"

    async def start_battle(self, dungeon_id: int = 1) -> bool:
        """场景1：开始战斗"""
        success, result = await self.send_game_action("start_run", "", dungeon_id)
        if success:
            self.update_status(result)
            logger.info(f"{self.account.index} | 战斗开始 - 我方血量: {self.player['health']}, 护盾: {self.player['shield']}, "
                        f"敌人血量: {self.enemy['health']}, 护盾: {self.enemy['shield']}")
            return True
        return False

    async def fight_enemy(self) -> bool:
        """场景2：与敌人战斗"""
        while True:
            if self.player["health"] <= 0:
                logger.info(f"{self.account.index} | 我方被击败 - 我方血量: {self.player['health']}, 敌人血量: {self.enemy['health']}")
                return False
            if self.enemy["health"] <= 0 and self.enemy["shield"] <= 0:
                loot_details = (
                    f"loot_one: {self.loot_options[0] if len(self.loot_options) > 0 else '无'}, "
                    f"loot_two: {self.loot_options[1] if len(self.loot_options) > 1 else '无'}, "
                    f"loot_three: {self.loot_options[2] if len(self.loot_options) > 2 else '无'}"
                )
                logger.info(f"{self.account.index} | 敌人被击败 - 我方血量: {self.player['health']}, "
                            f"战利品选项: {loot_details}")
                return True

            next_move = await self.analyze_next_move()
            success, result = await self.send_game_action(next_move, self.current_action_token)
            if not success:
                return False

            self.update_status(result)
            logger.info(f"{self.account.index} | 双方动作 - 我方: {next_move}, 敌方: {self.last_enemy_move}")
            logger.info(f"{self.account.index} | 当前状态 - 我方血量: {self.player['health']}, 护盾: {self.player['shield']}, "
                        f"出招: [rock: ATK={self.player['moves']['rock']['currentATK']}, DEF={self.player['moves']['rock']['currentDEF']}, Charges={self.player['moves']['rock']['currentCharges']}, "
                        f"paper: ATK={self.player['moves']['paper']['currentATK']}, DEF={self.player['moves']['paper']['currentDEF']}, Charges={self.player['moves']['paper']['currentCharges']}, "
                        f"scissor: ATK={self.player['moves']['scissor']['currentATK']}, DEF={self.player['moves']['scissor']['currentDEF']}, Charges={self.player['moves']['scissor']['currentCharges']}], "
                        f"敌人血量: {self.enemy['health']}, 护盾: {self.enemy['shield']}, "
                        f"出招: [rock: ATK={self.enemy['moves']['rock']['currentATK']}, DEF={self.enemy['moves']['rock']['currentDEF']}, Charges={self.enemy['moves']['rock']['currentCharges']}, "
                        f"paper: ATK={self.enemy['moves']['paper']['currentATK']}, DEF={self.enemy['moves']['paper']['currentDEF']}, Charges={self.enemy['moves']['paper']['currentCharges']}, "
                        f"scissor: ATK={self.enemy['moves']['scissor']['currentATK']}, DEF={self.enemy['moves']['scissor']['currentDEF']}, Charges={self.enemy['moves']['scissor']['currentCharges']}]")

            if result.get("message") == "Dungeon run room result reported":
                logger.info(f"{self.account.index} | 房间结束 - 我方血量: {self.player['health']}")
                return self.player["health"] > 0

            await asyncio.sleep(3)

    async def handle_loot(self) -> bool:
        """场景3：选择战利品"""
        loot_action = await self.choose_loot()
        success, result = await self.send_game_action(loot_action, self.current_action_token)
        if not success:
            return False

        self.update_status(result)
        logger.info(f"{self.account.index} | 战利品已选择 - 我方血量: {self.player['health']}, 护盾: {self.player['shield']}, "
                    f"出招: [rock: ATK={self.player['moves']['rock']['currentATK']}, DEF={self.player['moves']['rock']['currentDEF']}, Charges={self.player['moves']['rock']['currentCharges']}, "
                    f"paper: ATK={self.player['moves']['paper']['currentATK']}, DEF={self.player['moves']['paper']['currentDEF']}, Charges={self.player['moves']['paper']['currentCharges']}, "
                    f"scissor: ATK={self.player['moves']['scissor']['currentATK']}, DEF={self.player['moves']['scissor']['currentDEF']}, Charges={self.player['moves']['scissor']['currentCharges']}]")
        return True

    async def run(self):
        """主循环：战斗+战利品+继续"""
        if not await self.start_battle(dungeon_id=1):
            return

        while self.player["health"] > 0:
            battle_result = await self.fight_enemy()
            if not battle_result:
                logger.info(f"{self.account.index} | 战斗失败，游戏结束")
                break

            if not await self.handle_loot():
                logger.info(f"{self.account.index} | 战利品选择失败，停止")
                break

            logger.info(f"{self.account.index} | ==================进入下一敌人=====================")

        logger.info(f"{self.account.index} | 游戏结束 - {'我方被击败' if self.player['health'] <= 0 else '所有敌人被击败'}")

async def main():
    # 你的token
    token = "eyJhbGciOiJIUzI1NiJ9.eyJhZGRyZXNzIjoiMHg4ZjQ2OEIxY0JGRjUwRjk3OTEwOGM3OWY0NTc0OURDMjEzODUyRjY0IiwidXNlciI6eyJfaWQiOiI2N2Q0MTY0NTE4NDc5ZDc1YTA1MTQ3YmEiLCJ3YWxsZXRBZGRyZXNzIjoiMHg4ZjQ2OGIxY2JmZjUwZjk3OTEwOGM3OWY0NTc0OWRjMjEzODUyZjY0IiwidXNlcm5hbWUiOiIweDhmNDY4QjFjQkZGNTBGOTc5MTA4Yzc5ZjQ1NzQ5REMyMTM4NTJGNjQiLCJjYXNlU2Vuc2l0aXZlQWRkcmVzcyI6IjB4OGY0NjhCMWNCRkY1MEY5NzkxMDhjNzlmNDU3NDlEQzIxMzg1MkY2NCIsIl9fdiI6MH0sImdhbWVBY2NvdW50Ijp7Im5vb2IiOnsiQ09OU1VNQUJMRVNfQ0lEIjpbXSwiX2lkIjoiNjdkNDE2YzhjMDg2ZGZjZTdlODhkNzg4IiwiZG9jSWQiOiI0Nzg5MSIsInRhYmxlTmFtZSI6IkdpZ2FOb29iTkZUIiwidGFibGVJZCI6IjB4YjBjYjlkNWJhYzdiYjk2MTAyYzFhMGNlYzEyYTU3ZTk2ZTg2MDM0Yjk3MTZiOTljYTJlZDlkODFlNjFiYjlkYiIsImNvbFNldERhdGEiOnsiT1dORVJfQ0lEIjp7ImJsb2NrX251bWJlciI6NDExNTk4MCwibG9nX2luZGV4Ijo3NSwidHJhbnNhY3Rpb25faW5kZXgiOjE0fSwiSVNfTk9PQl9DSUQiOnsiYmxvY2tfbnVtYmVyIjo0MTE1OTgwLCJsb2dfaW5kZXgiOjc3LCJ0cmFuc2FjdGlvbl9pbmRleCI6MTR9LCJJTklUSUFMSVpFRF9DSUQiOnsiYmxvY2tfbnVtYmVyIjo0MTE1OTgwLCJsb2dfaW5kZXgiOjc5LCJ0cmFuc2FjdGlvbl9pbmRleCI6MTR9LCJMQVNUX1RSQU5TRkVSX1RJTUVfQ0lEIjp7ImJsb2NrX251bWJlciI6NDExNTk4MCwibG9nX2luZGV4Ijo3MiwidHJhbnNhY3Rpb25faW5kZXgiOjE0fSwiTEVWRUxfQ0lEIjp7ImJsb2NrX251bWJlciI6NDExNTk4MCwibG9nX2luZGV4Ijo3OCwidHJhbnNhY3Rpb25faW5kZXgiOjE0fX0sIk9XTkVSX0NJRCI6IjB4OGY0NjhiMWNiZmY1MGY5NzkxMDhjNzlmNDU3NDlkYzIxMzg1MmY2NCIsImNyZWF0ZWRBdCI6IjIwMjUtMDMtMTRUMTE6NDU6MTIuNzYwWiIsInVwZGF0ZWRBdCI6IjIwMjUtMDMtMTRUMTE6NDU6MTcuMjM4WiIsIl9fdiI6MCwiSVNfTk9PQl9DSUQiOnRydWUsIklOSVRJQUxJWkVEX0NJRCI6dHJ1ZSwiTEFTVF9UUkFOU0ZFUl9USU1FX0NJRCI6MTc0MTk1MjcwOCwiTEVWRUxfQ0lEIjoxfSwiYWxsb3dlZFRvQ3JlYXRlQWNjb3VudCI6dHJ1ZSwiY2FuRW50ZXJHYW1lIjp0cnVlLCJub29iUGFzc0JhbGFuY2UiOjAsImxhc3ROb29iSWQiOjQ5MDE3LCJtYXhOb29iSWQiOjEwMDAwfSwiZXhwIjoxNzQyMjIyMjQwfQ.Rs8_AhgxUEY6ijTDlrzwhdaAyDfBUyufKlcvF7s67Hc"
    # 创建客户端
    client = GameClient(token=token)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())