FWaaS internal
==============

FWaaSの構造
-----------
  L3NATAgentにFWaaS関連のモジュール(#1)を組み込むことで実現している。何か特殊なエージェントが別に起動するわけではない。
  (#1) firewall_l3_agent.FWaaSL3AgentRpcCallback

firewall_l3_agent.FWaaSL3AgentRpcCallback 
------------------------------------------
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

class FirewallCallbacks(n_rpc.RpcCallback) ★プラグイン側
--------------------------------------------------------
[ファイル]
neutron/services/firewall/fwaas_plugin.py

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

firewall_db.Firewall_db_mixin: ★プラグイン側
--------------------------------------------
  
