===========================================================
meteringの解析
===========================================================

クラスの関係(一部、クラスでないコンポーネントレベルのものも含む)
==================================================================

class MeteringPlugin(MeteringDbMixinをmixin)@neutron-server
  ↓ uses                                           ↑  
class MeteringAgentNotifyAPI@neutron-server        ↑  messaging
  ↓ messaging                                      ↑
AMQP                                              AMQP
  ↓ messaging                                      ↑  messaging
class MeteringAgent -----------------------> class MeteringPluginRpc
  ↓                       uses
  ↓ uses
class Driver




ファイル一覧
==============

./db/metering/metering_db.py(MeteringDbMixin)
neutron-serverが実行するmetering関連のDB操作メソッド群
中心となるクラスはMeteringDbMixin。

./db/metering/metering_rpc.py
meteringプラグインが使用するagentからのRPCのコールバック。

./db/migration/alembic_migrations/versions/569e98a8132b_metering.py
meteringlabels, meteringlabelrulesのテーブル作成用マイグレーションファイル

./services/metering/metering_plugin.py(MeteringPlugin)
neutron-server側のプラグインの実装。中心となるクラスは以下。
"class MeteringPlugin(metering_db.MeteringDbMixin):"

./api/rpc/agentnotifiers/metering_rpc_agent_api.py(MeteringAgentNotifyAPI)
MeteringAgentへのRPCメソッド群。neutron-serverが実行する。
MeteringPluginが使っている。

./services/metering/agents/metering_agent.py
./services/metering/drivers/abstract_driver.py
./services/metering/drivers/noop/noop_driver.py
./services/metering/drivers/iptables/__init__.py
./services/metering/drivers/iptables/iptables_driver.py
./extensions/metering.py



