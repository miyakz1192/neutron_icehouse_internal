===========================================
AMQP周りの初期調査メモ
===========================================

management consoleと本家のvisualizer
--------------------------------------

以下のコマンドを実行すると、インストールが可能::

  sudo rabbitmq-plugins enable rabbitmq_management_visualiser

しかし、非常に出来がわるい。どう操作したら良いかが全然わからない。

参考URL::
  
  http://www.thegeekstuff.com/2013/10/enable-rabbitmq-management-plugin/ 


亜流のvisualizer
------------------

こちらも良いかと思ったのだが、import時に、x/y座標を抜かすと、
描画ができないのでＮＧ。レイアウトを手で実行する必要がある様子。
あくまで参考レベルか。::

  https://github.com/jmcle/rabbitmq-visualizer

可視化のために
-----------------

management consoleをインストールすると、REST-APIを使えるらしい::

  http://hg.rabbitmq.com/rabbitmq-management/raw-file/rabbitmq_v3_3_4/priv/www/api/index.html


-------------------------------------------
reply queueを作る条件(openvswitch agent)
-------------------------------------------

openvswitch_agentがprepare_devices_filterメソッドで、self.plugin_rpc.security_group_rules_for_devicesを実行するときに、neutron-serverからの応答を受け取るためにreply queueを作る。::


  (Pdb) bt
    /usr/local/bin/neutron-openvswitch-agent(9)<module>()
  -> load_entry_point('neutron==2014.1.4.dev76', 'console_scripts', 'neutron-openvswitch-agent')()
    /opt/stack/neutron/neutron/plugins/openvswitch/agent/ovs_neutron_agent.py(1476)main()
  -> agent.daemon_loop()
    /opt/stack/neutron/neutron/plugins/openvswitch/agent/ovs_neutron_agent.py(1404)daemon_loop()
  -> self.rpc_loop(polling_manager=pm)
    /opt/stack/neutron/neutron/plugins/openvswitch/agent/ovs_neutron_agent.py(1337)rpc_loop()
  -> ovs_restarted)
    /opt/stack/neutron/neutron/plugins/openvswitch/agent/ovs_neutron_agent.py(1141)process_network_ports()
  -> port_info.get('updated', set()))
    /opt/stack/neutron/neutron/agent/securitygroups_rpc.py(257)setup_port_filters()
  -> self.prepare_devices_filter(new_devices)
    /opt/stack/neutron/neutron/agent/securitygroups_rpc.py(161)prepare_devices_filter()
  -> self.context, list(device_ids))
    /opt/stack/neutron/neutron/agent/securitygroups_rpc.py(86)security_group_rules_for_devices()
  -> topic=self.topic)
    /opt/stack/neutron/neutron/openstack/common/rpc/proxy.py(125)call()
  -> result = rpc.call(context, real_topic, msg, timeout)
    /opt/stack/neutron/neutron/openstack/common/rpc/__init__.py(112)call()
  -> return _get_impl().call(CONF, context, topic, msg, timeout)
    /opt/stack/neutron/neutron/openstack/common/rpc/impl_kombu.py(818)call()
  -> rpc_amqp.get_connection_pool(conf, Connection))
    /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py(576)call()
  -> rv = multicall(conf, context, topic, msg, timeout, connection_pool)
    /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py(566)multicall()
  -> connection_pool.reply_proxy = ReplyProxy(conf, connection_pool)
  > /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py(196)__init__()
  -> self._reply_q = 'reply_' + uuid.uuid4().hex











