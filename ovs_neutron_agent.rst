============================================
OVSNeutronAgent
============================================


OVSNeutronAgent
================

daemon_loop::

    def daemon_loop(self):
        with polling.get_polling_manager(
            self.minimize_polling,
            self.root_helper,
            self.ovsdb_monitor_respawn_interval) as pm:

            self.rpc_loop(polling_manager=pm)


OVSNeutronAgentの処理の中核。polling.get_polling_managerにより、
polling_managerが有効になる(pm変数として使える)、そのコンテキストのなかで、rpc_loopが呼ばれる。"with polling.get_polling_manager"でrpc_loopがくくられている。rpc_loopが終了すると、pmが自動的に終了するようになっている。

local_vlan_map
================

network(uuid)とlocal vlan idのマッピングを保持。
以下のようなコードにて、作成::

  self.local_vlan_map[net_uuid] = LocalVLANMapping(lvid,
                                                   network_type,
                                                   physical_network,
                                                   segmentation_id)

rpc_loopでネットワーク処理が行われる条件
==========================================

以下のコード::

  if self._agent_has_updates(polling_manager) or ovs_restarted:


