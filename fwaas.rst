FWaaS internal(icehouse)
========================

FWaaSの構造
-----------
  L3NATAgentにFWaaS関連のモジュール(#1)を組み込むことで実現している。何か特殊なエージェントが別に起動するわけではない。
  (#1) firewall_l3_agent.FWaaSL3AgentRpcCallback

firewall_l3_agent.FWaaSL3AgentRpcCallback ★エージェント側
---------------------------------------------------------
[ファイル]

neutron/services/firewall/agents/l3reference/firewall_l3_agent.py

  -  __init__
      - **説明：各種初期化を行う**
      - fwaas_plugin_configured and fwaas_enabledがfalseの場合、は異常終了
      - fwaas_enabledがtrueの場合、fwaas_driverを読み込み。
      - self.services_sync = Falseに設定(何?)
      - fwplugin_rcpのセットアップ

  -  _get_router_info_list_for_tenant(self, routers, tenant_id)

      - **説明：所有者がtenant_idかつ、自分(l3 agnet)が担当しており、かつ、network namespaceが起動しているrouterをroutersから探してリストで返す**
      - routersの中から、tenant_idに一致するrouter情報を抽出(router_ids)
      - router_idsの中のrouterで、自分(l3 agent)が担当していないrouterはスキップ
      - router_idsの中のrouterで、そのrouterのnetwork namespaceが起動している場合は、router_info_listにrouter idを追加
      - router_info_listを返却
 
  - _invoke_driver_for_plugin_api(self, context, fw, func_name)

      - **説明：self.fwaas_driverのfunc_nameを呼び出す(呼び出す前後で処理がある。func_nameを呼び出す前にrouterのチェック。tenantにrouterが無い場合は、なにもしない。func_nameを呼び出した後、その結果に応じてstatusを変化させる(fwがadmin_state_upの場合、ACTIVE。そう出ない場合はDOWN。fw_ext.FirewallInternalDriverError:の場合はERROR))**

      - neutron serverからすべてのルータの情報を取得(self.plugin_rpc.get_routers(context))★この処理は大変重くないか？
      -  _get_router_info_list_for_tenantでrouter絞り込み。結果をrouter_info_listに代入
      - もし、router_info_listが[]の場合、かつ、func_nameが"delete_firewall"の場合、self.fwplugin_rpc.firewall_deleted(context, fw['id')]を実行してreturn。もし、router_info_listが[]の場合、かつ、func_nameが"delete_firewall"でない場合はreturn
      - router_info_listが[]出ない場合、以降を実行
      - self.fwaas_driverのfunc_nameを呼び出す(引数：router_info_list,fw)
      - もし、fw["admin_state_up"]が真の場合、status = constants.ACTIVE。偽の場合、status = constants.DOWN。fw_ext.FirewallInternalDriverError:が発生した場合は、status = constants.ERROR
      - func_name == "delete_firewall"の場合、かつ、statusがconstants.ACTIVEまたは、constants.DOWNの場合、self.fwplugin_rpc.firewall_deleted(context, fw['id'])を呼び出す
      - func_nameが"delete_firewall"でない場合、self.fwplugin_rpc.set_firewall_status(context,fw['id'],status)を実行。

  -  _invoke_driver_for_sync_from_plugin(self, ctx, router_info_list, fw)

      - **説明:fwのstatusに応じてfwaas_driverのメソッドを呼ぶ(PENDING_DELETE -> delete_firewall, それ以外、update_firewall)**
      - fw['status'] == constants.PENDING_DELETE:の場合、self.fwaas_driver.delete_firewall(router_info_list, fw)を実行し、self.fwplugin_rpc.firewall_deletedを実行する。例外が発生した場合は、self.fwplugin_rpc.set_firewall_status(constants.ERROR)でエラー状態へ遷移する。
      - fw['status'] == constants.PENDING_DELETE:以外の場合(PENDING_UPDATE, PENDING_CREATE, ...)、self.fwaas_driver.update_firewall(router_info_list, fw)を実行する。実行後fw['admin_state_up']:の場合、statusをACTIVEにする。fw['admin_state_up']:以外の場合、statusをDOWNにする。update_firewallで例外が発生した場合、ERROR状態へ遷移する。

  - _process_router_add(self, ri):

    - **説明：ルータが追加された場合、そのルータ(ri)に対してself._invoke_driver_for_sync_from_pluginを適用する**
    - routers配列を[]で初期化して、riを追加。
    - self._get_router_info_list_for_tenant(routers,ri.router['tenant_id'])を実行(結果をrouter_info_listで受ける)
    - router_info_listが空でない場合、self.fwplugin_rpc.get_firewalls_for_tenant(ctx)を実行し、該当テナントのFWリストを得る(fw_listで受ける)。fw_listのそれぞれに対して、self._invoke_driver_for_sync_from_plugin(router_info_list,fw)を実行。

  - process_router_add(self, ri):

    - **説明：_process_router_addのラッパ**
    - self.fwaas_enabledがFalseの場合、return
    - self._process_router_add(ri)を実行する。例外が発生した場合、self.services_sync = Trueを実行。

  - process_services_sync(self, ctx):

    - **説明：すべてのFWの適用を、FWに対応したルータに対して行う**
    - self.fwaas_enabledがFalseの場合、return
    - self.plugin_rpc.get_routers(ctx)ですべてのrouterを取得(routersで受ける)
    - self.fwplugin_rpc.get_tenants_with_firewalls(ctx)でFWを持っているテナントのリストを得る(tenant_idsで受ける)
    - tenant_idsのそれぞれのidに対して、以下を実行
     - self.fwplugin_rpc.get_firewalls_for_tenant(ctx)でtenantが持っているFWのリストを得る(fw_listで受ける)
     - fw_listが空でないばあい、以下を実行

       - self._get_router_info_list_for_tenant(routers,tenant_id)を実行し、テナントのrouterを得る(router_info_listで受ける)
       - router_info_listが空でない場合、fw_listのそれぞれに対して以下を実行
         - self._invoke_driver_for_sync_from_plugin(ctx,router_info_list,fw)


  - create_firewall(self, context, firewall, host)

    - _invoke_driver_for_plugin_api(context,firewall,'create_firewall')を実行する


  - update_firewall(self, context, firewall, host)

    - _invoke_driver_for_plugin_api(context,firewall,'update_firewall')を実行する

   
  - delete_firewall(self, context, firewall, host)

    - _invoke_driver_for_plugin_api(context,firewall,'delete_firewall')を実行する

FWaaS driver処理 ★エージェント側
---------------------------------

FWaaSのDriverは以下のとおり::

  driver = neutron.services.firewall.drivers.linux.iptables_fwaas.IptablesFwaasDriver

今回はIptablesFwaasDriverについて調査する。
ファイル名::

  neutron/services/firewall/drivers/linux/iptables_fwaas.py


class IptablesFwaasDriver(fwaas_base.FwaasDriverBase):★エージェント側
----------------------------------------------------------------------

  - __init__(self):
      - **説明：初期化**
      - debugメッセージだけを出して何もしない

  - create_firewall(self, apply_list, firewall):
      - **説明：firewall を作成する**
      - firewall['admin_state_up']が指定されている場合
          + self._setup_firewall(apply_list, firewall)
      - firewall['admin_state_up']が指定されていない場合
          + self.apply_default_policy(apply_list, firewall)
      - 上記処理で例外が発生した場合、fw_ext.FirewallInternalDriverError(driver=FWAAS_DRIVER_NAME)raiseする

  - delete_firewall(self, apply_list, firewall):
      - **説明：firewall を削除する**
      - fwid = firewall['id']
      - apply_listの個々についてloop(router_info)
          + router_infoからiptbles_managerを取得(ipt_mgr)
          + self._remove_chains(fwid, ipt_mgr)を実行してchainを削除
          + self._remove_default_chains(ipt_mgr)を実行してdefault chain削除
          + ipt_mgr.defer_apply_off()を実行して、即座に変更を反映(apply the changes immediately (no defer in firewall path)
      - 上記処理で例外が発生した場合は、fw_ext.FirewallInternalDriverError(driver=FWAAS_DRIVER_NAME)をraise

  - update_firewall(self, apply_list, firewall):
      - **説明：firewall を更新する(処理内容はcreate_firewallと同じ)**
      - firewall['admin_state_up']が指定されている場合
          + self._setup_firewall(apply_list, firewall)
      - firewall['admin_state_up']が指定されていない場合
          + self.apply_default_policy(apply_list, firewall)
      - 上記処理で例外が発生した場合、fw_ext.FirewallInternalDriverError(driver=FWAAS_DRIVER_NAME)raiseする

  - apply_default_policy(self, apply_list, firewall):
      - **説明：defauly policyを適用する**
      - fwid = firewall['id']
      - apply_listの個々をループ(router_info)
          + ipt_mgr = router_info.iptables_manager
          + chainとdefault chainを削除(the following only updates local memory; no hole in FW)
          + default policy chainを追加し、policy chainを有効化する(defaultのDROP ALL policy chainを作成する)
          + ipt_mgr.defer_apply_off()で即座に変更を反映する
      - 上記処理で例外が発生した場合は、fw_ext.FirewallInternalDriverError(driver=FWAAS_DRIVER_NAME)をraiseする

  - _setup_firewall(self, apply_list, firewall):
      - **説明：firewallをセットアップする(apply_default_policyと処理は同じ)**
      - fwid = firewall['id']
      - apply_listの個々をループ(router_info)
          + ipt_mgr = router_info.iptables_manager
          + chainとdefault chainを削除(the following only updates local memory; no hole in FW)
          + default policy chainを追加し、policy chainを有効化する(defaultのDROP ALL policy chainを作成する)
          + ipt_mgr.defer_apply_off()で即座に変更を反映する
      - 上記処理で例外が発生した場合は、fw_ext.FirewallInternalDriverError(driver=FWAAS_DRIVER_NAME)をraiseする

  - _get_chain_name(self, fwid, ver, direction):
      - **説明：chain nameを返す**
      - "iv4<firewall id>"(input ipv4の場合)
      - "ov4<firewall id>"(output ipv4の場合)
      - "iv6<firewall id>"(input ipv6の場合)
      - "ov6<firewall id>"(output ipv6の場合)

      コードは以下::

        def _get_chain_name(self, fwid, ver, direction):
            return '%s%s%s' % (CHAIN_NAME_PREFIX[direction],
                              IP_VER_TAG[ver],
                              fwid)

  - _setup_chains(self, firewall, ipt_mgr):
      - **説明：chainをセットアップする**
      - invalid packet ruleとallow established ruleを追加する
      - firewall['firewall_rule_list']に指定されたruleを追加する

      コードは以下::

       def _setup_chains(self, firewall, ipt_mgr):
          """Create Fwaas chain using the rules in the policy
          """
          fw_rules_list = firewall['firewall_rule_list']
          fwid = firewall['id']
  
          #default rules for invalid packets and established sessions
          invalid_rule = self._drop_invalid_packets_rule()
          est_rule = self._allow_established_rule()
  
          for ver in [IPV4, IPV6]:
              if ver == IPV4:
                  table = ipt_mgr.ipv4['filter']
              else:
                  table = ipt_mgr.ipv6['filter']
              ichain_name = self._get_chain_name(fwid, ver, INGRESS_DIRECTION)
              ochain_name = self._get_chain_name(fwid, ver, EGRESS_DIRECTION)
              for name in [ichain_name, ochain_name]:
                  table.add_chain(name)
                  table.add_rule(name, invalid_rule)
                  table.add_rule(name, est_rule)
  
          for rule in fw_rules_list:
              if not rule['enabled']:
                  continue
              iptbl_rule = self._convert_fwaas_to_iptables_rule(rule)
              if rule['ip_version'] == 4:
                  ver = IPV4
                  table = ipt_mgr.ipv4['filter']
              else:
                  ver = IPV6
                  table = ipt_mgr.ipv6['filter']
              ichain_name = self._get_chain_name(fwid, ver, INGRESS_DIRECTION)
              ochain_name = self._get_chain_name(fwid, ver, EGRESS_DIRECTION)
              table.add_rule(ichain_name, iptbl_rule)
              table.add_rule(ochain_name, iptbl_rule)
          self._enable_policy_chain(fwid, ipt_mgr)

  - _remove_default_chains(self, nsid):
      - **説明：default のchainを削除する(第一引数にはiptables_managerが入る)**

      - コードは以下::

         def _remove_default_chains(self, nsid):
             """Remove fwaas default policy chain."""
             self._remove_chain_by_name(IPV4, FWAAS_DEFAULT_CHAIN, nsid)
             self._remove_chain_by_name(IPV6, FWAAS_DEFAULT_CHAIN, nsid)
     
  - _remove_chains(self, fwid, ipt_mgr):
      - **説明：chainを消去する**
      - コードは以下::

          def _remove_chains(self, fwid, ipt_mgr):
              """Remove fwaas policy chain."""
              for ver in [IPV4, IPV6]:
                  for direction in [INGRESS_DIRECTION, EGRESS_DIRECTION]:
                      chain_name = self._get_chain_name(fwid, ver, direction)
                      self._remove_chain_by_name(ver, chain_name, ipt_mgr)
      
  - _add_default_policy_chain_v4v6(self, ipt_mgr):
      - **説明：default policy chain(DROP ALL)を追加する**
      - コードは以下::

         def _add_default_policy_chain_v4v6(self, ipt_mgr):
             ipt_mgr.ipv4['filter'].add_chain(FWAAS_DEFAULT_CHAIN)
             ipt_mgr.ipv4['filter'].add_rule(FWAAS_DEFAULT_CHAIN, '-j DROP')
             ipt_mgr.ipv6['filter'].add_chain(FWAAS_DEFAULT_CHAIN)
             ipt_mgr.ipv6['filter'].add_rule(FWAAS_DEFAULT_CHAIN, '-j DROP')
     
  - _remove_chain_by_name(self, ver, chain_name, ipt_mgr):
      - **説明：chainをname指定で削除する**
      - コードは以下::

         def _remove_chain_by_name(self, ver, chain_name, ipt_mgr):
             if ver == IPV4:
                 ipt_mgr.ipv4['filter'].ensure_remove_chain(chain_name)
             else:
                 ipt_mgr.ipv6['filter'].ensure_remove_chain(chain_name)
     
  - _add_rules_to_chain(self, ipt_mgr, ver, chain_name, rules):
      - **説明：chainにruleを追加する**
      - コードは以下::

         def _add_rules_to_chain(self, ipt_mgr, ver, chain_name, rules):
             if ver == IPV4:
                 table = ipt_mgr.ipv4['filter']
             else:
                 table = ipt_mgr.ipv6['filter']
             for rule in rules:
                 table.add_rule(chain_name, rule)
     
  - _enable_policy_chain(self, fwid, ipt_mgr):
      - **説明：policy chainを有効化する**
      - FORWARD chainに、neutron-l3-agent-iv43a98286f(input)やneutron-l3-agent-ov43a98286f(output)へのjumpをルールを追加
      - FORWARD chainにinputとoutputのFWAAS_DEFAULT_CHAINへのjumpルールを追加(inputとoutputでDROP ALL)
      - コードは以下::

         def _enable_policy_chain(self, fwid, ipt_mgr):
             bname = iptables_manager.binary_name
     
             for (ver, tbl) in [(IPV4, ipt_mgr.ipv4['filter']),
                                (IPV6, ipt_mgr.ipv6['filter'])]:
                 for direction in [INGRESS_DIRECTION, EGRESS_DIRECTION]:
                     chain_name = self._get_chain_name(fwid, ver, direction)
                     chain_name = iptables_manager.get_chain_name(chain_name)
                     if chain_name in tbl.chains:
                         jump_rule = ['%s qr-+ -j %s-%s' % (IPTABLES_DIR[direction],
                                                            bname, chain_name)]
                         self._add_rules_to_chain(ipt_mgr, ver, 'FORWARD',
                                                  jump_rule)
     
             #jump to DROP_ALL policy
             chain_name = iptables_manager.get_chain_name(FWAAS_DEFAULT_CHAIN)
             jump_rule = ['-o qr-+ -j %s-%s' % (bname, chain_name)]
             self._add_rules_to_chain(ipt_mgr, IPV4, 'FORWARD', jump_rule)
             self._add_rules_to_chain(ipt_mgr, IPV6, 'FORWARD', jump_rule)
     
             #jump to DROP_ALL policy
             chain_name = iptables_manager.get_chain_name(FWAAS_DEFAULT_CHAIN)
             jump_rule = ['-i qr-+ -j %s-%s' % (bname, chain_name)]
             self._add_rules_to_chain(ipt_mgr, IPV4, 'FORWARD', jump_rule)
             self._add_rules_to_chain(ipt_mgr, IPV6, 'FORWARD', jump_rule)
            

class FirewallCallbacks(n_rpc.RpcCallback) ★プラグイン側
--------------------------------------------------------
[ファイル]
neutron/services/firewall/fwaas_plugin.py

[概要]
AMQPのイベントごとに実行されるコールバックの定義

  - __init__(self, plugin):
 
    - **説明：初期化を実施**
    - super(FirewallCallbacks, self).__init__()
    - self.plugin = plugin

  - set_firewall_status(self, context, firewall_id, status, **kwargs):
   
    - **説明：Firewallのstatusを変更する。ただし、PENDING_DELETEの場合は変更しない**
    - self.plugin._get_firewall(context, firewall_id)でfwを取得する
    - fwの状態がPENDING_STATUSの場合はFalseで返る
    - statusが(const.ACTIVE, const.INACTIVE, const.DOWN)のいずれかの場合はfwのstatusを更新してTrueで返る
    - statusが上記以外であれば、ERRORをfwにセットしてFalseで返る

  - firewall_deleted(self, context, firewall_id, **kwargs):

    - **説明：firewallをdeleted状態にするために、Agnetが使うRPCメソッド**
    - self.plugin._get_firewall(context, firewall_id)でfwを取得する
    - fwの状態がconst.PENDING_DELETEまたは、const.ERRORの場合
      - DBからfwを削除する
      - Trueで返る
    - fwの状態が上記以外の場合
      - fwの状態をERRORにセットする
      - Falseで返る
 
  - get_firewalls_for_tenant(self, context, **kwargs):
    
    - **説明: tenantのfirewallを得る(ルールあり)**
    - self.plugin.get_firewalls(context)を呼び出し、返ってくる個々のfwに対して、self.plugin._make_firewall_dict_with_rules(context, fw['id'])を呼び出しdictに変換して返す 

  - get_firewalls_for_tenant_without_rules(self, context, **kwargs):
    
    - **説明：tenantのfirewallを得る(ルールなし)**
    - self.plugin.get_firewalls(context)を呼び出し、返ってくるものをリスト化して返す

  - get_tenants_with_firewalls(self, context, **kwargs):
      - **説明：firewallを所有しているtenantを得る(agentがfirewallを保持するすべてのテナントを得るために使用する)**
      - neutron_context.get_admin_context()で管理者コンテキストを得る
      - self.plugin.get_firewalls(ctx)でfirewallを得る
      - tenant_idでフィルタリングしてfwのリストを返す


class FirewallAgentApi(n_rpc.RpcProxy): ★プラグイン側
--------------------------------------------------------
[ファイル]
neutron/services/firewall/fwaas_plugin.py

[概要]
プラグイン側のagentのRPC APIを呼び出すためのラッパー

  -  __init__(self, topic, host):
      - **説明：各種初期化を行う**
      - self.hostにhostを代入する

  -  create_firewall(self, context, firewall):
      - **説明：firewallの作成を行う**
      - self.fanout_castを呼び出し、エージェントへ通知する
          - "create_firewall", firewall=firewal, host=self.host

  -  update_firewall(self, context, firewall):
      - **説明：firewallの更新を行う**
      - self.fanout_castを呼び出し、エージェントへ通知する
          - "update_firewall", firewall=firewal, host=self.host

  -  delete_firewall(self, context, firewall):
      - **説明：firewallの削除を行う**
      - self.fanout_castを呼び出し、エージェントへ通知する
          - "delete_firewall", firewall=firewal, host=self.host

class FirewallCountExceeded(n_exception.Conflict): ★プラグイン側
----------------------------------------------------------------
[ファイル]
neutron/services/firewall/fwaas_plugin.py

[概要]
Firewallの個数が超過したときに発生する例外

class FirewallPlugin(firewall_db.Firewall_db_mixin): ★プラグイン側
------------------------------------------------------------------
[ファイル]
neutron/services/firewall/fwaas_plugin.py

[概要]
Neutron Firewall Service Pluginの実装。FWaaS request/responseのワークフローを管理する。DB関連の仕事のほとんどはfirewall_db.Firewall_db_mixinで実装されている。

  -  __init__(self, topic, host):
      - **説明：各種初期化を行う(以下、各処理は要調査)**
      - qdbapi.register_models()でモデルの登録を行う
      - self.endpoints = [FirewallCallbacks(self)]でエンドポイントをFirewallCallbacksに設定
      - self.conn = n_rpc.create_connection(new=True)でAMQPサーバに接続する
      - AMQPにconsumerの設定を行う(topics=q-firewall-plugin,FirewallCallbacks,fanout=False)
      - agent_rpcの初期化を行う(FierwallAgentApi)

  -  _make_firewall_dict_with_rules(self, context, firewall_id):
      - **説明:rule付きのFirewallの情報を返す**
      - firewall_idでfirewallをDBから検索する
      - 検索結果からfirewall_policy_idを得る
      - firewall_policy_idがある場合
          - fw_policy_idでfireall_policyをDBから検索する
          - fw_policyの個々のfirewall_rulesについてrule_idでDBからFirewallRuleを検索する
          - firewall['firewall_rule_list']に結果を代入する
      - firewall_policy_idが存在しない場合、firewall['firewall_rule_list']に[]を代入する

      - 結果(firewall)を返却する
      - [メモ]このメソッドで作成されたfirewallオブジェクトのサイズが、rabbit/qpidがサポートするサイズを越えた場合、問題が発生する！！！

  - _rpc_update_firewall(self, context, firewall_id):
      - **説明：DBのFirewallの状態をupdateしたあとで、agentにupdateを通知する**
      - super(FirewallPlugin, self).update_firewallでfirewallの状態をPENDING_UPDATE状態に変更する
      - self._make_firewall_dict_with_rulesでfirewallの情報を得る。
      - self.agent_rpc.update_firewall(context, fw_with_rules)でagentにupdateの通知を行う

  - _rpc_update_firewall_policy(self, context, firewall_policy_id):
      - **説明：firewall_policy_idに関連付くfireweallの状態をPENDING_UPDATE状態に変更する**
      - firewall_policyのfirewall_listの各firewallについて、self._rpc_update_firewall(context, firewall_id)を実行する

  - _ensure_update_firewall(self, context, firewall_id):
      - **説明：firewallの状態がPENDING_CREATE or PENDING_UPDATE or PENDING_DELETEの場合はFirewallInPendingState例外を発生する**

  - _ensure_update_firewall_policy(self, context, firewall_policy_id):
      - **説明：firewall_policyに関連づくfirewallの状態をPENDING_UPDATE状態に設定する**
      - firewall_policy_idをキーとしてDBからfirewall_policyを検索する
      - policyが存在し、かつ、firewall_policyにfirewall_listが存在する場合は以下を実行
          - 各firewallについて、self._ensure_update_firewall(context, firewall_id)を実行する

  - _ensure_update_firewall_rule(self, context, firewall_rule_id):
      - **説明：firewall_ruleに関連づくfiewallの状態をupdateする**
      - firewall_rule_idをキーとしてDBからfirewall_ruleを検索する
      - fw_ruleが存在し、かつ、fw_ruleにfirewall_policy_idが存在する場合、self._ensure_update_firewall_policyを実行し、firewallの状態をPENDING_UPDATE状態に設定する

  - create_firewall(self, context, firewall):
      - **説明：firewallの作成を行う**
      - self._get_tenant_id_for_createでfirewallのtenant_idを得る。
      - self.get_firewalls_countでfirewallの個数を得る
      - fw_countがある場合、FirewallCountExceeded(tenant_id=tenant_id)例外をraiseする
      - firewallの状態をPENDING_CREATE状態に設定する
      - super(FirewallPlugin, self).create_firewall(context, firewall)を実行する(firewall_db.Firewall_db_mixin)
      - self._make_firewall_dict_with_rules(context, fw['id']))を実行してrule付きのfw情報を作る
      - self.agent_rpc.create_firewall(context, fw_with_rules)でfirewallがcreateされたことをagentに通知する
      - fw情報を返す


  - update_firewall(self, context, id, firewall):
      - **説明：firewallの状態を更新する**
      - self._ensure_update_firewall(context, id)でfirewallの状態をチェックする
      - firewallの状態をPENDING_UPDATEに設定する
      - fw = super(FirewallPlugin, self).update_firewall(context, id, firewall)を実行する(firewall_db.Firewall_db_mixin)
      - self._make_firewall_dict_with_rules(context, fw['id']))を実行してrule付きのfw情報を得る
      - self.agent_rpc.update_firewall(context, fw_with_rules)でagnetに状態の更新を通知する
      - fwを返す

  - delete_firewall(self, context, id):
      - **説明：firewallを削除する** 
      - fw = super(FirewallPlugin, self).update_firewallでfirewallの状態をPENDING_DELETEに設定する
      - self._make_firewall_dict_with_rules(context, fw['id']))でrule付きのfirewallの情報を作成する
      - self.agent_rpc.delete_firewall(context, fw_with_rules)でagentに状態の更新を通知する


  - update_firewall_policy(self, context, id, firewall_policy):
      - **説明：firewall policyを更新する**
      - self._ensure_update_firewall_policy(context, id)で状態をチェックする
      - fwp = super(FirewallPlugin,self).update_firewall_policy(context, id, firewall_policy)を実行する
      - self._rpc_update_firewall_policy(context, id)でagentに状態の更新を通知する
      - firewall ruleを返す

  - update_firewall_rule(self, context, id, firewall_rule):
      - **説明：firewall ruleを更新する**
      - self._ensure_update_firewall_rule(context, id)で状態をチェックする
      - fwr = super(FirewallPlugin,self).update_firewall_rule(context, id, firewall_rule)を実行する
      - self._rpc_update_firewall_policy(context, firewall_policy_id)でagentに通知する

  - insert_rule(self, context, id, rule_info):
      - **説明：ruleをinsertする**
      - self._ensure_update_firewall_policy(context, id)で状態をチェックする
      - fwp = super(FirewallPlugin,self).insert_rule(context, id, rule_info)を実行する
      - self._rpc_update_firewall_policy(context, id)でagnetに通知する

  - remove_rule(self, context, id, rule_info):
      - **説明：ruleをremoveする**
      - self._ensure_update_firewall_policy(context, id)で状態をチェックする
      - fwp = super(FirewallPlugin,self).remove_rule(context, id, rule_info)を実行する
      - self._rpc_update_firewall_policy(context, id)を実行してagentに通知する

DBレコード構造★
---------------

[ファイル]
neutron/db/firewall/firewall_db.py

- class FirewallRule(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant)
    + PK:ID
    + FK:firewall_policies.id

- class Firewall(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    + PK:ID
    + FK:firewall_policies.id

- class FirewallPolicy(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    + PK:ID
    + firewall_rules = orm.relationship(
        FirewallRule,
        backref=orm.backref('firewall_policies', cascade='all, delete'),
        order_by='FirewallRule.position',
        collection_class=ordering_list('position', count_from=1))
    + ordering_listについては、以下を参照
        + http://docs.sqlalchemy.org/en/rel_0_9/orm/extensions/orderinglist.html


firewall_db.Firewall_db_mixin: ★プラグイン側
--------------------------------------------
  
[ファイル]
neutron/db/firewall/firewall_db.py

[概要]
firewall pluginのDB関連の処理を行うmixin

  - _core_plugin(self):
      - **説明：プラグインを返す**

  - _get_firewall(self, context, id):
      - **説明：firewallをidをキーとして検索する**
      - self._get_by_id(context, Firewall, id)でレコードを検索する
      - ※例外をキャッチして、NoResultFountの場合はfirewall.FirewallNotFound(firewall_id=id)をraiseする

  - _get_firewall_policy(self, context, id):
      - **説明：firewall policyを返す**
      - return self._get_by_id(context, FirewallPolicy, id)
      - ※例外をキャッチして、NoResultFountの場合はfirewall.FirewallPolicyNotFound(firewall_policy_id=id)をraiseする

  - _get_firewall_rule(self, context, id):
      - **説明：firewall ruleを返す**
      - return self._get_by_id(context, FirewallRule, id)
      - ※例外をキャッチして、NoResultFountの場合はfirewall.FirewallRuleNotFound(firewall_rule_id=id)をraiseする

  - _make_firewall_dict(self, fw, fields=None):
      - **説明：firewall情報をdictにして返す**

  - _make_firewall_policy_dict(self, firewall_policy, fields=None):
      - **説明：firewall policy情報をdictにして返す**

  - _make_firewall_rule_dict(self, firewall_rule, fields=None):
      - **説明：firewall rule情報をdictにして返す**

  - _set_rules_for_policy(self, context, firewall_policy_db, rule_id_list):
      - **説明：firewall_policy(firewall_policy_db)にrule(rule_id_list)を設定する(policyに関連付くrulesは一旦リセットされ、rule_id_listに指定されたrulesが新たに設定される)**
      - context.session.begin(subtransactions=True):を実行する
      - fwp_db = firewall_policy_dbを実行する
      - rule_id_listが無い場合、fwp_db.firewall_rulesに[]を設定し、fwp_db.audited=Falseに設定してreturnする
      - rule_id_listからidを抽出してリスト化する(filters変数にセット)
      - self._get_collection_queryを使って、filtersをキーとしてfirewall ruleをDBから検索する(rules_in_db変数にセット)
      - 検索結果のrules_in_dbからdictを生成する(rule_dict変数にセット)
      - rule_id_listをループ(fwrule_id)
          + fwrule_idがrules_dictに含まれていない場合は、firewall.FirewallRuleNotFoundをraiseする
          + rules_dict[fwrule_id]['firewall_policy_id']が、fwp_db['id']と異なる場合は、firewall.FirewallRuleInUseをraiseする
      - fwp_db.firewall_rulesを[]に設定し、rule_id_listで更新する
      - fwp_db.firewall_rules.reorder()
      - fwp_db.audited = False
 
  - _process_rule_for_policy(self, context, firewall_policy_id, firewall_rule_db, position):
      - **説明：firewall_policyからfirewall_ruleをinstertまたはremoveする**
      - fwp_queryを取得する
      - firewall_policy_idをキーとしてDBを検索し、先頭を得る
      - positionが真の場合
          + fwp_db.firewall_rules.insert(position - 1, firewall_rule_db)
      - positionが偽の場合
          + fwp_db.firewall_rules.remove(firewall_rule_db)
      - fwp_dbをリオーダーする(fwp_db.firewall_rules.reorder())
      - auditedをFalse(fwp_db.audited = False)
      - fwp_dbをdictにして返す(return self._make_firewall_policy_dict(fwp_db))

  - _get_min_max_ports_from_range(self, port_range):
      - **説明：port_rangeを[min,max]にして返す**
  
  - _get_port_range_from_min_max_ports(self, min_port, max_port):
      - **説明：[min,max]からport_range"min:max"にして返す**

  - _validate_fwr_protocol_parameters(self, fwr):
      - **説明：protocol parameterのを行い、不正な場合はfirewall.FirewallRuleInvalidICMPParameterをraiseする**
      - fwr['protocol']がconst.TCPでない、かつ、const.UDPでない
          + fwr['source_port'] または、fwr['destination_port']が設定されている場合、firewall.FirewallRuleInvalidICMPParameterをraise

  -  create_firewall(self, context, firewall):
      - **説明：firewallの作成を行う**
      - self._get_tenant_id_for_create(context, fw)でテナントIDを取得する
      - Firewallレコードを作成する
          + firewall_db = Firewall(id=uuidutils.generate_uuid(),
              +                    tenant_id=tenant_id,
              +                    name=fw['name'],
              +                    description=fw['description'],
              +                    firewall_policy_id=
              +                    fw['firewall_policy_id'],
              +                    admin_state_up=fw['admin_state_up'],
              +                    status=const.PENDING_CREATE)
          + ★idは指定できない！！！

      - self._make_firewall_dict(firewall_db)の実行結果を返す

  -  update_firewall(self, context, id, firewall):
      - **説明：firewallのを更新を行う**
      - firewall情報をidをキーとして検索する
      - firewallをupdateする
      - self._make_firewall_dict(firewall_db)の実行結果を返す

  -  delete_firewall(self, context, id):
      - **説明：firewallの削除を行う**
      - firewall情報をidをキーとして検索する
      - firewallをdeleteする

  -  get_firewall(self, context, id, fields=None):
      - **説明：firewallの情報を返す**
      - firewall情報をidをキーとして検索する
      - return self._make_firewall_dict(fw, fields)

  -  get_firewalls(self, context, filters=None, fields=None):
      - **説明：firewallの情報を返す**
      - return self._get_collection(context, Firewall,
          +                         self._make_firewall_dict,
          +                         filters=filters, fields=fields)

  -  get_firewalls_count(self, context, filters=None):
      - **説明：firewallの個数を返す**
      - return self._get_collection_count(context, Firewall,filters=filters)

  -  create_firewall_policy(self, context, firewall_policy):
      - **説明：firewall polcyの作成を行う**
      - self._get_tenant_id_for_create(context, fwp)でテナントIDを得る
      - FirewallPolicyのDBレコードを作成する
      - context.session.add(fwp_db)でレコードをコミットする
      - _set_rules_for_policyでpolicyにruleを設定する
      - return self._make_firewall_policy_dict(fwp_db)を返す

  -  update_firewall_policy(self, context, id, firewall_policy):
      - **説明：firewall polcyの更新を行う**
      - self._get_firewall_policy(context, id)でpolicyの検索を行う
      - self._set_rules_for_policyでfirewall policyの作成を行う
      - 引数として与えられたfirewall_policyにautitedが指定されていない場合は、fwp変数を更新し、DBレコードのauditedフィールドをFalseに設定するようにする(次のfwp_db.update(fwp))
      - DBを更新する
      - return self._make_firewall_policy_dict(fwp_db)を返す

  -  delete_firewall_policy(self, context, id):
      - **説明：firewall polcyの削除を行う**
      - self._get_firewall_policy(context, id)でfirewall policyを検索
      - 検索結果のfirewall policyのidをキーとしてFirewallテーブルを検索(firewall policyがFirewallで使用されているかをチェック)
          + 使用されている場合：firewall.FirewallPolicyInUse(firewall_policy_id=id)
          + 使用されていない場合、firewall policyをDBから削除

  - get_firewall_policy(self, context, id, fields=None):
      - **説明：firewall polcyの取得を行う**
      - DBから検索して、その結果をself._make_firewall_policy_dict(fwp, fields)して返す

  - get_firewall_policies(self, context, filters=None, fields=None):
      - **説明：複数のfirewall polcyの取得を行う**

  - get_firewalls_policies_count(self, context, filters=None):
      - **説明：複数のfirewall polcyの個数の取得を行う**

  - create_firewall_rule(self, context, firewall_rule):
      - **説明：firewall ruleの作成を行う**
      - self._validate_fwr_protocol_parameters(fwr)でprotocolのチェックを行う
      - self._get_tenant_id_for_create(context, fwr)でtenant idの取得を行う
      - source port のmin maxを得る
      - dest port のmin maxを得る
      - FirewallRuleのDBレコードを登録する
      - self._make_firewall_rule_dict(fwr_db)を返す

  - update_firewall_rule(self, context, id, firewall_rule):
      - **説明：firewall ruleの更新を行う**
      - 引数のfirewall_ruleにsource portが指定されていた場合、fwr変数(firewall rule更新用の変数)に設定する
      - 引数のfirewall_ruleにdest portが指定されていた場合、fwr変数(firewall rule更新用の変数)に設定する
      - self._get_firewall_rule(context, id)でfirewall ruleを検索する
      - DBのupdateを行う
      - もし、firewall ruleにfirewall_policy_idが設定されている場合、firewall policyのauditedをFalseに設定する
      - return self._make_firewall_rule_dict(fwr_db)を返す

  - delete_firewall_rule(self, context, id):
      - **説明：firewall ruleの削除を行う**
      - 削除対象のfirewall ruleがfirewall policyに設定されていた場合、firewall.FirewallRuleInUse(firewall_rule_id=id)をraiseする
      - DBからfirewall ruleを削除する。

  - get_firewall_rule(self, context, id, fields=None):
      - **説明：firewall ruleの取得を行う**

  - get_firewall_rules(self, context, filters=None, fields=None):
      - **説明：複数のfirewall ruleの取得を行う**

  - get_firewalls_rules_count(self, context, filters=None):
      - **説明：firewall ruleの個数を返す**

  - _validate_insert_remove_rule_request(self, id, rule_info):
      - **説明：ruleのinsert/removeリクエストのチェックを行う**
      - rule_infoが未指定、または、rule_infoにfirewall_rule_idが無い場合は、firewall.FirewallRuleInfoMissing()をraiseする

  - insert_rule(self, context, id, rule_info):
      - **説明：ruleのinsertを行う**
      - _validate_insert_remove_rule_request(self, id, rule_info):でチェックを行う
      - insert_before変数をTrueに設定する
      - ref_firewall_rule_idをNoneに設定する
      - rule_infoにfirewall_rule_idが無い場合は、firewall.FirewallRuleNotFound(firewall_rule_id=None)をraiseする
      - rule_infoにinsert_beforeが存在する場合、ref_firewall_rule_id変数に、rule_info['insert_before']を設定
      - ref_firewall_rule_id変数がNoneであり、かつ、'insert_after'がrule_infoに指定されていた場合、ref_firewall_rule_id変数に、rule_info['insert_after']を設定（※insert_beforeとinsert_afterの両方が設定されていた場合は、insert_beforeが使用されるという仕様）
      - insert_before変数をFalseに設定
      - 引数firewall_rule_idのfirewall ruleがすでに、とあるfirewall policyで使われている場合は、firewall.FirewallRuleInUse(firewall_rule_id=fwr_db['id'])をraise
      - ref_firewall_rule_id変数が設定されている場合、
          + insert_beforeがTrueの場合、positionにrule_info['insert_before'](=ref_firewall_rule_id)のpositionを代入する
          + insert_beforeがTrueでない場合、positionにrule_info['insert_after'](=ref_firewall_rule_id)のposition+1を代入する
      - ref_firewall_rule_id変数が設定されていない場合、
          + positionを1に設定する(要するにルールの先頭)
      - self._process_rule_for_policy(context, id, fwr_db,position)の実行結果を返す(最終的にfirewall policyの情報をdictにしたもを返す)

  - remove_rule(self, context, id, rule_info):
      - **説明：ruleのremoveを行う**
      - self._validate_insert_remove_rule_request(id, rule_info)でリクエストをチェック
     - rule_info['firewall_rule_id']にfirewall_rule_idが設定されていない場合は、firewall.FirewallRuleNotFound(firewall_rule_id=None)をraiseする
     - rule_infoに含まれるfirewall_rule_idを参照してDBから検索
     - 検索結果のfirewall_ruleのIDと引数のidが一致しない場合は、firewall.FirewallRuleNotAssociatedWithPolicyをraiseする
     - self._process_rule_for_policy(context, id, fwr_db, None)の結果を返す
         + 指定したruleがpolicyから削除される(rule自体はDBからは消去されない)
         + 最終的にはfirewall policyのdictが返る


番外(fieldsのフィルタリング)
----------------------------

neutronのAPIではGET系であれば取得するfieldを選択(filter)できる。それは、neutron-erverのコードでは以下のように行われている(FWaaSの場合。neutronの他のリソースでも同じと考えられる)::

    def get_firewall_policy(self, context, id, fields=None):
        LOG.debug(_("get_firewall_policy() called"))
        fwp = self._get_firewall_policy(context, id)
        return self._make_firewall_policy_dict(fwp, fields)

get_firewall_policyにfieldsを指定することで、欲しいfieldを取得できる。処理的には、self._make_firewall_policy_dictで行われている。::

    def _make_firewall_policy_dict(self, firewall_policy, fields=None):
        fw_rules = [rule['id'] for rule in firewall_policy['firewall_rules']]
        firewalls = [fw['id'] for fw in firewall_policy['firewalls']]
        res = {'id': firewall_policy['id'],
               'tenant_id': firewall_policy['tenant_id'],
               'name': firewall_policy['name'],
               'description': firewall_policy['description'],
               'shared': firewall_policy['shared'],
               'audited': firewall_policy['audited'],
               'firewall_rules': fw_rules,
               'firewall_list': firewalls}
        return self._fields(res, fields)

このメソッドの引数fieldsが、このメソッドの中で一度も使われずに、そのままself._fields(res, fields)に渡されている。::

    def _fields(self, resource, fields):
        if fields:
            return dict(((key, item) for key, item in resource.items()
                         if key in fields))
        return resource

つまり、DBの検索結果として生成したdictを上記のように単純にフィルターしているだけである。DBの機能を使ってフィルターが実現されている訳ではない。railsでは自分の欲しいfieldだけをDBから抽出する機能があるが、neutron-serverが利用しているpythonのsqlarchemyではrailsのような機能が無いためだろか、DBから取ってきた情報を自前でフィルターしている。filterを指定すると、それなりにneutron-serverの負荷が増えるのではないかと思う。

ところで、get_firewall_policyは単数だが、複数のpolicyの情報を取得するmethodも用意されている。::

    def get_firewall_policies(self, context, filters=None, fields=None):
        LOG.debug(_("get_firewall_policies() called"))
        return self._get_collection(context, FirewallPolicy,
                                    self._make_firewall_policy_dict,
                                    filters=filters, fields=fields)

このメソッドは、_get_collectionにより複数の情報を取得している。_get_collectionに_make_firewall_policy_dictが渡されていることに注目すべき。::

    def _get_collection(self, context, model, dict_func, filters=None,
                        fields=None, sorts=None, limit=None, marker_obj=None,
                        page_reverse=False):
        query = self._get_collection_query(context, model, filters=filters,
                                           sorts=sorts,
                                           limit=limit,
                                           marker_obj=marker_obj,
                                           page_reverse=page_reverse)
        items = [dict_func(c, fields) for c in query]
        if limit and page_reverse:
            items.reverse()
        return items

つまり、複数取得できた結果の個々の要素に対して、dict_func=make_firewall_policy_dictを実行しているだけである。


