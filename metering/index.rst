===========================================================
meteringの解析
===========================================================

クラスの関係
============


MeteringPlugin(MeteringDbMixinをmixin)









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

./services/metering/agents
./services/metering/agents/metering_agent.py
./services/metering/drivers/abstract_driver.py
./services/metering/drivers/noop/noop_driver.py
./services/metering/drivers/iptables/__init__.py
./services/metering/drivers/iptables/iptables_driver.py
./api/rpc/agentnotifiers/metering_rpc_agent_api.py
./extensions/metering.py



