認証・認可系の処理
==================

認可の処理(リソースの作成編)
============================

ここのキモは、ユーザが指定したアクション(例：create_network)および、リソースの属性(例：name,shared,...)を元にmatch_ruleを作成する事。match_ruleには、必ず、アクションが先頭に来て、その次にリソースの属性のmatch_ruleが来る。ユーザが指定しなかった属性についてはmatch_ruleが作成されない。例えば、以下のユーザがあったとして、::

     OS_PASSWORD=a
     OS_AUTH_URL=http://192.168.122.36:5000/v2.0/
     OS_USERNAME=user1
     OS_TENANT_NAME=admin
     LESSCLOSE=/usr/bin/lesspipe %s %s
     
このユーザは_member_ロールであって、かつ、以下のコマンドを実行したとする。::

     neutron net-create shared1 --shared
     
この時、name=shared1, shared=Trueが指定されているため、match_ruleの構造は以下になる。なお、enforce_policy指定されている属性のみmatch_ruleとして現れる。nameは指定されてないのでmatch_ruleには現れない。::

    match_rule = action=create_network And shared=True

match_ruleとpolicy.jsonから生成したルール(_rules)の照合を行っていく。

+----------------------+----------------------------+
| match_rule(from user)|      _rules(policy.json)   |
+======================+============================+
|create_network        |   create_network -> True   | 
+----------------------+----------------------------+
|create_network:shared |   create_network:shared -> |
|                      |   admin_only            -> |
|                      |   context_is_admin         | 
+----------------------+----------------------------+

さて、ソースを追っていく。

policy.enforceの呼び出し元は以下。なお、api-paste.iniで指定するフックとして呼び出される処理ではないらしい。::

    def create(self, request, body=None, **kwargs):
        """Creates a new instance of the requested entity."""
        parent_id = kwargs.get(self._parent_id_name)
        notifier_api.notify(request.context,
                            self._publisher_id,
                            self._resource + '.create.start',
                            notifier_api.CONF.default_notification_level,
                            body)
        body = Controller.prepare_request_body(request.context, body, True,
                                               self._resource, self._attr_info,
                                               allow_bulk=self._allow_bulk)
        action = self._plugin_handlers[self.CREATE]
        # Check authz                                                                     
        if self._collection in body:
            # Have to account for bulk create                                             
            items = body[self._collection]
            deltas = {}
            bulk = True
        else:
            items = [body]
            bulk = False
        # Ensure policy engine is initialized                                             
        policy.init()
        for item in items:
            self._validate_network_tenant_ownership(request,
                                                    item[self._resource])
            policy.enforce(request.context,
                           action,
                           item[self._resource])
            try:
                tenant_id = item[self._resource]['tenant_id']
                count = quota.QUOTAS.count(request.context, self._resource,
                                           self._plugin, self._collection,
                                           tenant_id)
                if bulk:
                    delta = deltas.get(tenant_id, 0) + 1
                    deltas[tenant_id] = delta
                else:
                    delta = 1
                kwargs = {self._resource: count + delta}
            except exceptions.QuotaResourceUnknown as e:
                # We don't want to quota this resource                                    
                LOG.debug(e)
            else:
                quota.QUOTAS.limit_check(request.context,
                                         item[self._resource]['tenant_id'],
                                         **kwargs)

enforceのコードは以下::


     def enforce(context, action, target, plugin=None):
         """Verifies that the action is valid on the target in this context.
     
         :param context: neutron context
         :param action: string representing the action to be checked
             this should be colon separated for clarity.
         :param target: dictionary representing the object of the action
             for object creation this should be a dictionary representing the
             location of the object e.g. ``{'project_id': context.project_id}``
         :param plugin: currently unused and deprecated.
             Kept for backward compatibility.
     
         :raises neutron.exceptions.PolicyNotAuthorized: if verification fails.
         """
     
         rule, target, credentials = _prepare_check(context, action, target)
         result = policy.check(rule, target, credentials, action=action)
         if not result:
             LOG.debug(_("Failed policy check for '%s'"), action)
             raise exceptions.PolicyNotAuthorized(action=action)
         return result
     
引数の例は以下のとおり::

     (Pdb) a
     context = <neutron.context.Context object at 0x4f86f10>
     action = get_network
     target = {'status': u'ACTIVE', 'subnets': [u'aaad9a32-fc42-447d-9e88-29343d9e0ef8'], 'name': u'VirtualInterfacesTestJSON-2105663723-network', 'provider:physical_network': None, ' admin_state_up': True, 'tenant_id': u'bd93671560894383a661d935d98ad6db', 'provider:network_type': u'local', 'router:external': False, 'shared': False, 'id': u'2e6dc779-12ad-4e52-aff9-c15401f2111b', 'provider:segmentation_id': None}
     plugin = None
     (Pdb) 

それが、_prepara_checkに渡されてゆく::

     def _prepare_check(context, action, target):
         """Prepare rule, target, and credentials for the policy engine."""
         # Compare with None to distinguish case in which target is {}
         if target is None:
             target = {}
         match_rule = _build_match_rule(action, target)
         credentials = context.to_dict()
         return match_rule, target, credentials

_build_match_rulehは以下。::

     def _build_match_rule(action, target):
         """Create the rule to match for a given action.
     
         The policy rule to be matched is built in the following way:
         1) add entries for matching permission on objects
         2) add an entry for the specific action (e.g.: create_network)
         3) add an entry for attributes of a resource for which the action
            is being executed (e.g.: create_network:shared)
         4) add an entry for sub-attributes of a resource for which the
            action is being executed
            (e.g.: create_router:external_gateway_info:network_id)
         """
         match_rule = policy.RuleCheck('rule', action)
         resource, is_write = get_resource_and_action(action)
         # Attribute-based checks shall not be enforced on GETs
         if is_write:
             # assigning to variable with short name for improving readability
             res_map = attributes.RESOURCE_ATTRIBUTE_MAP
             if resource in res_map:
                 for attribute_name in res_map[resource]:
                     if _is_attribute_explicitly_set(attribute_name,
                                                     res_map[resource],
                                                     target):
                         attribute = res_map[resource][attribute_name]
                         if 'enforce_policy' in attribute:
                             attr_rule = policy.RuleCheck('rule', '%s:%s' %
                                                          (action, attribute_name))
                             # Build match entries for sub-attributes, if present
                             validate = attribute.get('validate')
                             if (validate and any([k.startswith('type:dict') and v
                                                   for (k, v) in
                                                   validate.iteritems()])):
                                 attr_rule = policy.AndCheck(
                                     [attr_rule, _build_subattr_match_rule(
                                         attribute_name, attribute,
                                         action, target)])
                             match_rule = policy.AndCheck([match_rule, attr_rule])
         return match_rule

このメソッドのキモは、ユーザが指定したアクション(例：create_network)および、リソースの属性(例：name,shared,...)を元にmatch_ruleを作成する事。match_ruleには、必ず、アクションが先頭に来て、その次にリソースの属性のmatch_ruleが来る。ユーザが指定しなかった属性についてはmatch_ruleが作成されない。例えば、以下のユーザがあったとして、::

     OS_PASSWORD=a
     OS_AUTH_URL=http://192.168.122.36:5000/v2.0/
     OS_USERNAME=user1
     OS_TENANT_NAME=admin
     LESSCLOSE=/usr/bin/lesspipe %s %s
     
このユーザは_member_ロールであって、かつ、以下のコマンドを実行したとする。::

     neutron net-create shared1 --shared
     
この時、name=shared1, shared=Trueが指定されているため、match_ruleの構造は以下になる。なお、enforce_policy指定されている属性のみmatch_ruleとして現れる。nameは指定されてないのでmatch_ruleには現れない。::

    match_rule = action=create_network And shared=True

以降、enforceメソッドの中のpolicy.checkでは以下の順番に、policy.jsonから生成したルール(_rules)と照合を行っていく。

+----------------------+----------------------------+
| match_rule(from user)|      _rules(policy.json)   |
+======================+============================+
|create_network        |   create_network -> True   | 
+----------------------+----------------------------+
|create_network:shared |   create_network:shared -> |
|                      |   admin_only            -> |
|                      |   context_is_admin         | 
+----------------------+----------------------------+

この場合は、2つめのcreate_network:sharedのルール照合で、contest_is_adminのところで条件がFalse(admin is not in [_member_]:API発行ユーザのロールにadminが含まれていない)になるため、認可に失敗して、コマンドは結局以下のエラーになる(403:forbidden)。::

     miyakz@icehouse:/etc/neutron$ neutron net-create shared1 --shared
     Policy doesn't allow create_network to be performed.
     miyakz@icehouse:/etc/neutron$ 
     
なお、"create_router:external_gateway_info:enable_snat"などのサブ属性は、_build_subattr_match_ruleの中でmatch_ruleが生成される（確認未)。

コード中のattributes.RESOURCE_ATTRIBUTE_MAPの値は以下。この定数自体はapi/v2/attributes.pyで定義されている。多分どこかで、各extentionの同名の定数が連結されている::          
          
     (Pdb) p attributes.RESOURCE_ATTRIBUTE_MAP
     {'subnets': {'ipv6_ra_mode': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'validate': {'type:values': ['dhcpv6-stateful', 'dhcpv6-stateless', 'slaac']}, 'allow_put': True, 'allow_post': True}, 'allocation_pools': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'validate': {'type:ip_pools': None}, 'allow_put': False, 'allow_post': True}, 'host_routes': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_to': <function convert_none_to_empty_list at 0x2d510c8>, 'validate': {'type:hostroutes': None}}, 'ipv6_address_mode': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'validate': {'type:values': ['dhcpv6-stateful', 'dhcpv6-stateless', 'slaac']}, 'allow_put': True, 'allow_post': True}, 'cidr': {'is_visible': True, 'validate': {'type:subnet': None}, 'allow_put': False, 'allow_post': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'enable_dhcp': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'network_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'allow_post': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': False, 'allow_post': True}, 'dns_nameservers': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_to': <function convert_none_to_empty_list at 0x2d510c8>, 'validate': {'type:nameservers': None}}, 'gateway_ip': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'validate': {'type:ip_address_or_none': None}, 'allow_put': True, 'allow_post': True}, 'ip_version': {'convert_to': <function convert_to_int at 0x2d0ded8>, 'validate': {'type:values': [4, 6]}, 'allow_put': False, 'allow_post': True, 'is_visible': True}, 'shared': {'is_visible': False, 'allow_put': False, 'allow_post': False, 'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}}, 'firewall_rules': {'protocol': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'convert_to': <function convert_protocol at 0x4ac9488>, 'validate': {'type:values': [None, 'tcp', 'udp', 'icmp']}}, 'description': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'source_port': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'convert_to': <function convert_port_to_string at 0x4ac9578>, 'validate': {'type:port_range': None}}, 'source_ip_address': {'default': None, 'is_visible': True, 'validate': {'type:ip_or_subnet_or_none': None}, 'allow_put': True, 'allow_post': True}, 'destination_ip_address': {'default': None, 'is_visible': True, 'validate': {'type:ip_or_subnet_or_none': None}, 'allow_put': True, 'allow_post': True}, 'firewall_policy_id': {'is_visible': True, 'validate': {'type:uuid_or_none': None}, 'allow_put': False, 'allow_post': False}, 'position': {'default': None, 'is_visible': True, 'allow_put': False, 'allow_post': False}, 'destination_port': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'convert_to': <function convert_port_to_string at 0x4ac9578>, 'validate': {'type:port_range': None}}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'enabled': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'action': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': 'deny', 'convert_to': <function convert_action_to_case_insensitive at 0x4ac9500>, 'validate': {'type:values': ['allow', 'deny']}}, 'ip_version': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': 4, 'convert_to': <function convert_to_int at 0x2d0ded8>, 'validate': {'type:values': [4, 6]}}, 'shared': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}}, 'routers': {'status': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'external_gateway_info': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'enforce_policy': True, 'validate': {'type:dict_or_nodata': {'network_id': {'type:uuid': None, 'required': True}, 'enable_snat': {'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required': False, 'type:boolean': None}}}}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'admin_state_up': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': False, 'allow_post': True}, 'routes': {'is_visible': True, 'allow_put': True, 'allow_post': False, 'default': <object object at 0x7f4f701ae150>, 'convert_to': <function convert_none_to_empty_list at 0x2d510c8>, 'validate': {'type:hostroutes': None}}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}}, 'quotas': {}, 'security_group_rules': {'remote_group_id': {'default': None, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'direction': {'is_visible': True, 'validate': {'type:values': ['ingress', 'egress']}, 'allow_put': True, 'allow_post': True}, 'remote_ip_prefix': {'default': None, 'is_visible': True, 'allow_put': False, 'allow_post': True, 'convert_to': <function convert_ip_prefix_to_cidr at 0x4af4050>}, 'protocol': {'default': None, 'is_visible': True, 'allow_put': False, 'allow_post': True, 'convert_to': <function convert_protocol at 0x4aede60>}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'ethertype': {'is_visible': True, 'allow_put': False, 'allow_post': True, 'default': 'IPv4', 'convert_to': <function convert_ethertype_to_case_insensitive at 0x4af4758>, 'validate': {'type:values': ['IPv4', 'IPv6']}}, 'port_range_min': {'default': None, 'convert_to': <function convert_validate_port_value at 0x4af4d70>, 'allow_put': False, 'allow_post': True, 'is_visible': True}, 'port_range_max': {'default': None, 'convert_to': <function convert_validate_port_value at 0x4af4d70>, 'allow_put': False, 'allow_post': True, 'is_visible': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'security_group_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}}, 'ports': {'status': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'extra_dhcp_opts': {'default': None, 'is_visible': True, 'validate': {'type:list_of_dict_or_none': {'opt_value': {'type:not_empty_string_or_none': None, 'required': True}, 'opt_name': {'type:not_empty_string': None, 'required': True}, 'id': {'type:uuid': None, 'required': False}}}, 'allow_put': True, 'allow_post': True}, 'binding:host_id': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'allow_put': True, 'allow_post': True, 'enforce_policy': True}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'allowed_address_pairs': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_list_to': <function convert_kvp_list_to_dict at 0x2d51050>, 'enforce_policy': True, 'validate': {'type:validate_allowed_address_pairs': None}}, 'admin_state_up': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'network_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'allow_post': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': False, 'allow_post': True}, 'binding:vif_details': {'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'allow_put': False, 'allow_post': False, 'is_visible': True}, 'binding:vnic_type': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': 'normal', 'enforce_policy': True, 'validate': {'type:values': ['normal', 'direct', 'macvtap']}}, 'binding:vif_type': {'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'allow_put': False, 'allow_post': False, 'is_visible': True}, 'device_owner': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'mac_address': {'is_visible': True, 'allow_put': False, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'validate': {'type:mac_address': None}}, 'binding:profile': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'validate': {'type:dict_or_none': None}}, 'fixed_ips': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_list_to': <function convert_kvp_list_to_dict at 0x2d51050>, 'enforce_policy': True, 'validate': {'type:fixed_ips': None}}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'security_groups': {'default': <object object at 0x7f4f701ae150>, 'is_visible': True, 'allow_put': True, 'allow_post': True, 'convert_to': <function convert_to_uuid_list_or_none at 0x4af4cf8>}, 'device_id': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}}, 'agents': {'description': {'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': False}, 'alive': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'topic': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'host': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'started_at': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'allow_post': False}, 'binary': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'admin_state_up': {'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': False, 'is_visible': True}, 'heartbeat_timestamp': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'agent_type': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'created_at': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'configurations': {'is_visible': True, 'allow_put': False, 'allow_post': False}}, 'firewall_policies': {'description': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'firewall_rules': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'convert_to': <function convert_none_to_empty_list at 0x2d510c8>, 'validate': {'type:uuid_list': None}}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'audited': {'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'shared': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}}, 'firewalls': {'status': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'firewall_policy_id': {'is_visible': True, 'validate': {'type:uuid_or_none': None}, 'allow_put': True, 'allow_post': True}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'admin_state_up': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'shared': {'is_visible': False, 'allow_put': True, 'allow_post': True, 'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'description': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}}, 'networks': {'status': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'subnets': {'default': [], 'is_visible': True, 'allow_put': False, 'allow_post': False}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': True, 'allow_post': True}, 'provider:physical_network': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'validate': {'type:string': None}}, 'admin_state_up': {'default': True, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'allow_put': True, 'allow_post': True, 'is_visible': True}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': False, 'allow_post': True}, 'segments': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_list_to': <function convert_kvp_list_to_dict at 0x2d51050>, 'enforce_policy': True, 'validate': {'type:convert_segments': None}}, 'provider:network_type': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'enforce_policy': True, 'validate': {'type:string': None}}, 'router:external': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}, 'shared': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': False, 'convert_to': <function convert_to_boolean at 0x2d0de60>, 'required_by_policy': True, 'enforce_policy': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'provider:segmentation_id': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': <object object at 0x7f4f701ae150>, 'convert_to': <type 'int'>, 'enforce_policy': True}}, 'security_groups': {'tenant_id': {'required_by_policy': True, 'is_visible': True, 'allow_put': False, 'allow_post': True}, 'description': {'default': '', 'is_visible': True, 'allow_put': True, 'allow_post': True}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}, 'security_group_rules': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'name': {'default': '', 'is_visible': True, 'validate': {'type:name_not_default': None}, 'allow_put': True, 'allow_post': True}}, 'floatingips': {'floating_network_id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'allow_post': True}, 'router_id': {'default': None, 'is_visible': True, 'validate': {'type:uuid_or_none': None}, 'allow_put': False, 'allow_post': False}, 'fixed_ip_address': {'default': None, 'is_visible': True, 'validate': {'type:ip_address_or_none': None}, 'allow_put': True, 'allow_post': True}, 'floating_ip_address': {'is_visible': True, 'validate': {'type:ip_address_or_none': None}, 'allow_put': False, 'allow_post': False}, 'tenant_id': {'required_by_policy': True, 'is_visible': True, 'validate': {'type:string': None}, 'allow_put': False, 'allow_post': True}, 'status': {'is_visible': True, 'allow_put': False, 'allow_post': False}, 'port_id': {'is_visible': True, 'allow_put': True, 'allow_post': True, 'default': None, 'required_by_policy': True, 'validate': {'type:uuid_or_none': None}}, 'id': {'is_visible': True, 'validate': {'type:uuid': None}, 'allow_put': False, 'primary_key': True, 'allow_post': False}}}
     (Pdb) 

クレデンシャル情報は以下。::

     (Pdb) p credentials
     {'project_name': u'admin', 'tenant_name': u'admin', 'timestamp': '2014-09-27 16:26:40.515133', 'is_admin': True, 'user': u'b97cef0b004f4e6fb6162b13045e1c13', 'tenant': u'bbf770e7cc7d499fba61abc002be7693', 'user_id': u'b97cef0b004f4e6fb6162b13045e1c13', 'roles': [u'_member_', u'admin', u'heat_stack_owner'], 'tenant_id': u'bbf770e7cc7d499fba61abc002be7693', 'read_deleted': 'no', 'request_id': 'req-5cf3dea3-c2bb-4b4c-8983-c7ca3b04cd41', 'project_id': u'bbf770e7cc7d499fba61abc002be7693', 'user_name': u'admin'}
     (Pdb) 

以降、enforceメソッドの中のpolicy.check(rule, target, credentials, action=action)に進んでゆく[openstack/common/policy.py]。::


     def check(rule, target, creds, exc=None, *args, **kwargs):
         """                                                                                   
         Checks authorization of a rule against the target and credentials.                    
                                                                                               
         :param rule: The rule to evaluate.                                                    
         :param target: As much information about the object being operated                    
                        on as possible, as a dictionary.                                       
         :param creds: As much information about the user performing the                       
                       action as possible, as a dictionary.                                    
         :param exc: Class of the exception to raise if the check fails.                       
                     Any remaining arguments passed to check() (both                           
                     positional and keyword arguments) will be passed to                       
                     the exception class.  If exc is not provided, returns                     
                     False.                                                                    
                                                                                               
         :return: Returns False if the policy does not allow the action and                    
                  exc is not provided; otherwise, returns a value that                         
                  evaluates to True.  Note: for rules using the "case"                         
                  expression, this True value will be the specified string                     
                  from the expression.                                                         
         """
     
         # Allow the rule to be a Check tree     
         if isinstance(rule, BaseCheck):
            result = rule(target, creds)
         elif not _rules:
             # No rules to reference means we're going to fail closed                          
             result = False
         else:
             try:
                 # Evaluate the rule                                                           
                 result = _rules[rule](target, creds)
             except KeyError:
                 # If the rule doesn't exist, fail closed                                      
                 result = False
     
         # If it is False, raise the exception if requested                                    
         if exc and result is False:
             raise exc(*args, **kwargs)
     
         return result
     
"result = rule(target, creds)"にすすんでゆく。_rulesはpolicy.jsonで定義したruleが定義されている::

     class RuleCheck(Check):
         def __call__(self, target, creds):
             """
             Recursively checks credentials based on the defined rules.
             """
     
             try:
                 return _rules[self.match](target, creds)
             except KeyError:
                 # We don't have any matching rule; fail closed
                 return False

create_networkのケースでは以下の要になっていて::
     
     (Pdb) p self.match
     'create_network'
     (Pdb) p _rules[self.match]
     <neutron.openstack.common.policy.TrueCheck object at 0x50dd250>
     (Pdb) 

単にTrueCheckが行われる::

     class TrueCheck(BaseCheck):
         """
         A policy check that always returns True (allow).
         """
     
         def __str__(self):
             """Return a string representation of this check."""
     
             return "@"
     
         def __call__(self, target, cred):
             """Check the policy."""
     
             return True

認可の処理(リソースの表示編)
==============================

リソースのshowでは、最初にアクション（例：get_network）の認可を行い、次にリソースの各属性の認可を行う。
     
neutron/api/v2/base.pyのshowメソッドは以下の構造になっている。::
            
     show 
      | 
      +->  _item -> policy.enforce(アクション:get_network等)
      +->  _view -> _exclude_attributes_by_policy -> policy.check(各属性)     

では、ソースの詳細を見てみる。

[ソース]
neutron/api/v2/base.py

[クラス]
Controller

showのソースはいかになっていて、_view以降でGETで見せるデータのフィルタを
行っている::
          
        def show(self, request, id, **kwargs):
             """Returns detailed information about the requested entity."""
             try:
                 # NOTE(salvatore-orlando): The following ensures that fields                  
                 # which are needed for authZ policy validation are not stripped               
                 # away by the plugin before returning.                                        
                 field_list, added_fields = self._do_field_list(
                     api_common.list_args(request, "fields"))
                 parent_id = kwargs.get(self._parent_id_name)
                 # Ensure policy engine is initialized                                         
                 policy.init()
                 return {self._resource:
                         self._view(request.context,
                                    self._item(request,
                                               id,
                                               do_authz=True,
                                               field_list=field_list,
                                               parent_id=parent_id),
                                    fields_to_strip=added_fields)}
             except exceptions.PolicyNotAuthorized:
                 # To avoid giving away information, pretend that it                           
                 # doesn't exist                                                               
                 msg = _('The resource could not be found.')
                 raise webob.exc.HTTPNotFound(msg)

以下のメソッドでpolcyチェックを実施::     

         def _exclude_attributes_by_policy(self, context, data):
             """Identifies attributes to exclude according to authZ policies.                  
                                                                                               
             Return a list of attribute names which should be stripped from the                
             response returned to the user because the user is not authorized                  
             to see them.                                                                      
             """
             attributes_to_exclude = []
             for attr_name in data.keys():
                 attr_data = self._attr_info.get(attr_name)
                 if attr_data and attr_data['is_visible']:
                     if policy.check(
                         context,
                         '%s:%s' % (self._plugin_handlers[self.SHOW], attr_name),
                         None,
                         might_not_exist=True):
                         # this attribute is visible, check next one                           
                         continue
                 # if the code reaches this point then either the policy check                 
                 # failed or the attribute was not visible in the first place                  
                 attributes_to_exclude.append(attr_name)
             return attributes_to_exclude

チェック対象の属性は以下のようにして求められる::

     (Pdb) p data.keys()
     ['status', 'subnets', 'name', 'provider:physical_network', 'admin_state_up', 'tenant_id',\
      'provider:network_type', 'router:external', 'shared', 'id', 'provider:segmentation_id']
     (Pdb)      
     (Pdb) p self._plugin_handlers[self.SHOW], attr_name
     ('get_network', 'status')
     (Pdb) 

以下、policy.check()の内容[neutron/policy.py]::

     def check(context, action, target, plugin=None, might_not_exist=False):
         """Verifies that the action is valid on the target in this context.                   
                                                                                               
         :param context: neutron context                                                       
         :param action: string representing the action to be checked                           
             this should be colon separated for clarity.                                       
         :param target: dictionary representing the object of the action                       
             for object creation this should be a dictionary representing the                  
             location of the object e.g. ``{'project_id': context.project_id}``                
         :param plugin: currently unused and deprecated.                                       
             Kept for backward compatibility.                                                  
         :param might_not_exist: If True the policy check is skipped (and the                  
             function returns True) if the specified policy does not exist.                    
             Defaults to false.                                                                
                                                                                               
         :return: Returns True if access is permitted else False.                              
         """
         if might_not_exist and not (policy._rules and action in policy._rules):
             return True
         return policy.check(*(_prepare_check(context, action, target)))

might_not_exist=Trueなので、アクションが定義されて意無い場合はTrueになる。
あれ、defaultのルールが適用されないぞ・・・？、例えば、get_network:provider:physical_networkだとpolicy.jsonに定義されているので、policy.checkが行われるが、get_network:nameなどは定義されていないため、Trueになる::

     (Pdb) p action
     'get_network:status'
     (Pdb) p policy._rules and action in policy._rules
     False
     (Pdb) 
          
roleがadminでない場合は、physical_networkは見れない。そこで、policy.jsonからphysical_networkに関するルールを削除した場合、roleがadminでなくても、physical_networkが見れるようになるか実験。::

     【physical_networkをpolicy.jsonから除く前】
     miyakz@icehouse:~$ neutron net-show aaa
     +-----------------+--------------------------------------+
     | Field           | Value                                |
     +-----------------+--------------------------------------+
     | admin_state_up  | True                                 |
     | id              | 0415753f-a189-461d-a0d8-284aa6c47e4b |
     | name            | aaa                                  |
     | router:external | False                                |
     | shared          | False                                |
     | status          | ACTIVE                               |
     | subnets         |                                      |
     | tenant_id       | bbf770e7cc7d499fba61abc002be7693     |
     +-----------------+--------------------------------------+
     miyakz@icehouse:~$ 
     
     【physical_networkをpolicy.jsonから除いた後】
     miyakz@icehouse:/etc/neutron$ neutron net-show aaa
     +---------------------------+--------------------------------------+
     | Field                     | Value                                |
     +---------------------------+--------------------------------------+
     | admin_state_up            | True                                 |
     | id                        | 0415753f-a189-461d-a0d8-284aa6c47e4b |
     | name                      | aaa                                  |
     | provider:physical_network |                                      |
     | router:external           | False                                |
     | shared                    | False                                |
     | status                    | ACTIVE                               |
     | subnets                   |                                      |
     | tenant_id                 | bbf770e7cc7d499fba61abc002be7693     |
     +---------------------------+--------------------------------------+
     miyakz@icehouse:/etc/neutron$ 
     
という感じで見れてしまう。
defaultは以下で定義されているようにみえるのだが::

     class Rules(dict):
         """                                                                                   
         A store for rules.  Handles the default_rule setting directly.                        
         """
     (snip)
         def __missing__(self, key):
             """Implements the default rule handling."""
     
             # If the default rule isn't actually defined, do something                        
             # reasonably intelligent                                                          
             if not self.default_rule or self.default_rule not in self:
                 raise KeyError(key)
     
             return self[self.default_rule]
     (snip)
     

認可の処理(context_is_admin)
=============================

neutron net-show <network>を実行した際のスタックトレース。::

     -> init()
     (Pdb) w
       /usr/local/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
     -> func(*args, **kwargs)
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(594)process_request()
     -> proto.__init__(sock, address, self)
       /usr/lib/python2.7/SocketServer.py(638)__init__()
     -> self.handle()
       /usr/lib/python2.7/BaseHTTPServer.py(340)handle()
     -> self.handle_one_request()
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(285)handle_one_request()
     -> self.handle_one_response()
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(389)handle_one_response()
     -> result = self.application(self.environ, start_response)
       /usr/lib/python2.7/dist-packages/paste/urlmap.py(203)__call__()
     -> return app(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
     -> response = req.get_response(self.application)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1320)send()
     -> application, catch_exc_info=False)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
     -> app_iter = application(self.environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
     -> response = req.get_response(self.application)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1320)send()
     -> application, catch_exc_info=False)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
     -> app_iter = application(self.environ, start_response)
       /opt/stack/python-keystoneclient/keystoneclient/middleware/auth_token.py(632)__call__()
     -> return self.app(env, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/auth.py(56)__call__()★1
     -> request_id=req_id)
       /opt/stack/neutron/neutron/context.py(70)__init__()★2
     -> self.is_admin = policy.check_is_admin(self)
     > /opt/stack/neutron/neutron/policy.py(376)check_is_admin()
     -> init()
     (Pdb) 
     
★1のあたり、auth.pyはキモとなる。user_id,tenant_id,roles,tenant_name,user_name,req_idをcontext.Contextクラスに詰め込んでreq.environ['neutron.context']に代入する。::

     class NeutronKeystoneContext(wsgi.Middleware):
         """Make a request context from keystone headers."""
     
         @webob.dec.wsgify
         def __call__(self, req):
             # Determine the user ID                                                                                                    
             user_id = req.headers.get('X_USER_ID')
             if not user_id:
                 LOG.debug(_("X_USER_ID is not found in request"))
                 return webob.exc.HTTPUnauthorized()
     
             # Determine the tenant                                                                                                     
             tenant_id = req.headers.get('X_PROJECT_ID')
     
             # Suck out the roles                                                                                                       
             roles = [r.strip() for r in req.headers.get('X_ROLES', '').split(',')]
     
             # Human-friendly names                                                                                                     
             tenant_name = req.headers.get('X_PROJECT_NAME')
             user_name = req.headers.get('X_USER_NAME')
     
             # Use request_id if already set                                                                                            
             req_id = req.environ.get(request_id.ENV_REQUEST_ID)
     
             # Create a context with the authentication data                                                                            
             ctx = context.Context(user_id, tenant_id, roles=roles,
                                   user_name=user_name, tenant_name=tenant_name,
                                   request_id=req_id)
     
             # Inject the context...                                                                                                    
             req.environ['neutron.context'] = ctx
     
             return self.application
     
context.Contextのところもキモ★2のあたり。policy.check_is_admin(self)が呼び出される。::

     class ContextBase(common_context.RequestContext):
         """Security context and request information.
     
         Represents the user taking a given action within the system.
     
         """
     
         def __init__(self, user_id, tenant_id, is_admin=None, read_deleted="no",
                      roles=None, timestamp=None, load_admin_roles=True,
                      request_id=None, tenant_name=None, user_name=None,
                      overwrite=True, **kwargs):
             """Object initialization.
     
             :param read_deleted: 'no' indicates deleted records are hidden, 'yes'
                 indicates deleted records are visible, 'only' indicates that
                 *only* deleted records are visible.
     
             :param overwrite: Set to False to ensure that the greenthread local
                 copy of the index is not overwritten.
     
             :param kwargs: Extra arguments that might be present, but we ignore
                 because they possibly came in from older rpc messages.
             """
             super(ContextBase, self).__init__(user=user_id, tenant=tenant_id,
                                               is_admin=is_admin,
                                               request_id=request_id)
             self.user_name = user_name
             self.tenant_name = tenant_name
     
             self.read_deleted = read_deleted
             if not timestamp:
                 timestamp = datetime.datetime.utcnow()
             self.timestamp = timestamp
             self._session = None
             self.roles = roles or []
             if self.is_admin is None:
                 self.is_admin = policy.check_is_admin(self)
             elif self.is_admin and load_admin_roles:
                 # Ensure context is populated with admin roles
                 admin_roles = policy.get_admin_roles()
                 if admin_roles:
                     self.roles = list(set(self.roles) | set(admin_roles))
             # Allow openstack.common.log to access the context
             if overwrite or not hasattr(local.store, 'context'):
                 local.store.context = self
     
             # Log only once the context has been configured to prevent
             # format errors.
             if kwargs:
                 LOG.debug(_('Arguments dropped when creating '
                             'context: %s'), kwargs)

check_is_adminの処理は以下のとおり。::

     def check_is_admin(context):
         """Verify context has admin rights according to policy settings."""
         import pdb
         pdb.set_trace()
         init()
         # the target is user-self                                                                                                      
         credentials = context.to_dict()
         target = credentials
         # Backward compatibility: if ADMIN_CTX_POLICY is not                                                                           
         # found, default to validating role:admin                                                                                      
         admin_policy = (ADMIN_CTX_POLICY in policy._rules
                         and ADMIN_CTX_POLICY or 'role:admin')
         return policy.check(admin_policy, target, credentials)

admin_policyあたりの処理は以下のような感じ::

     (Pdb) p ADMIN_CTX_POLICY in policy._rules
     True
     (Pdb) p ADMIN_CTX_POLICY or 'role:admin'
     'context_is_admin'
     (Pdb) p (ADMIN_CTX_POLICY in policy._rules and ADMIN_CTX_POLICY or 'role:admin')
     'context_is_admin'
     (Pdb) 
     
policy.check(admin_policy, target, credentials)が処理され、そのなかで、API要求ユーザがcontext_is_admin(adminかどうか)がチェックされる。もし、真であれば、contextのis_aminプロパティにTrueが設定される。その後、base.pyのdef showが呼び出される。def showでは大まかに以下の順番で処理が行われる。::


      １。ネットワークの一覧取得
　　　２。policy check

ネットワークの一覧取得の処理の延長で_model_queryが呼び出され、ここで、context.is_adminが偽あれば、テナントの絞り込みが行われ、真であれば、tenantの絞り込みは行われない（ここ、重要）::

         def _model_query(self, context, model):
             query = context.session.query(model)
             # define basic filter condition for model query                                                                            
             # NOTE(jkoelker) non-admin queries are scoped to their tenant_id                                                           
             # NOTE(salvatore-orlando): unless the model allows for shared objects                                                      
             query_filter = None
             if not context.is_admin and hasattr(model, 'tenant_id'):
                 if hasattr(model, 'shared'):
                     query_filter = ((model.tenant_id == context.tenant_id) |
                                     (model.shared == sql.true()))
                 else:
                     query_filter = (model.tenant_id == context.tenant_id)
             # Execute query hooks registered from mixins and plugins                                                                   
             for _name, hooks in self._model_query_hooks.get(model,
                                                             {}).iteritems():
                 query_hook = hooks.get('query')
                 if isinstance(query_hook, basestring):
                     query_hook = getattr(self, query_hook, None)
                 if query_hook:
                     query = query_hook(context, model, query)
     
                 filter_hook = hooks.get('filter')
                 if isinstance(filter_hook, basestring):
                     filter_hook = getattr(self, filter_hook, None)
                 if filter_hook:
                     query_filter = filter_hook(context, model, query_filter)
     
             # NOTE(salvatore-orlando): 'if query_filter' will try to evaluate the                                                      
             # condition, raising an exception                                                                                          
             if query_filter is not None:
                 query = query.filter(query_filter)
             return query

ネットの一覧取得が完了した次にpolicyのcheckが行われ、ネットワーク一覧情報を返すかどうかの判定が行われる::

   def _item(self, request, id, do_authz=False, field_list=None,
	      parent_id=None):
        """Retrieves and formats a single element of the requested entity."""
	kwargs = {'fields': field_list}
        action = self._plugin_handlers[self.SHOW]
        if parent_id:
	    kwargs[self._parent_id_name] = parent_id
	obj_getter = getattr(self._plugin, action)
        obj = obj_getter(request.context, id, **kwargs)
        # Check authz                                                                                                              
	# FIXME(salvatore-orlando): obj_getter might return references to                                                          
        # other resources. Must check authZ on them too.                                                                           
        if do_authz:
            policy.enforce(request.context, action, obj)
        return obj

policy.enforceでpolicy.jsonに記載しているルールに反した場合、例外が発生して、obj(ネットワーク一覧）はユーザに返却されない。
ルールに反して意無い場合は、objが返される。
     
認証の処理
============

neutron net-show <network name>(GET /v2.0/etworks.json?fields=id&id=network_id)の処理から見てみる
-----------------------------------------------------------------------------------------------------

デバッガで表示させたスタックトレース。以下、「★ココ！！」に着目::

     > /opt/stack/neutron/neutron/db/db_base_plugin_v2.py(1032)get_network()
     -> network = self._get_network(context, id)
     (Pdb) w
       /usr/local/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
     -> func(*args, **kwargs)
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(594)process_request()
     -> proto.__init__(sock, address, self)
       /usr/lib/python2.7/SocketServer.py(638)__init__()
     -> self.handle()
       /usr/lib/python2.7/BaseHTTPServer.py(340)handle()
     -> self.handle_one_request()
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(285)handle_one_request()
     -> self.handle_one_response()
       /usr/local/lib/python2.7/dist-packages/eventlet/wsgi.py(389)handle_one_response()
     -> result = self.application(self.environ, start_response)
       /usr/lib/python2.7/dist-packages/paste/urlmap.py(203)__call__()
     -> return app(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
     -> response = req.get_response(self.application)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1320)send()
     -> application, catch_exc_info=False)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
     -> app_iter = application(self.environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
     -> response = req.get_response(self.application)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1320)send()
     -> application, catch_exc_info=False)
       /usr/local/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
     -> app_iter = application(self.environ, start_response)
       /opt/stack/python-keystoneclient/keystoneclient/middleware/auth_token.py(632)__call__()★ココ！！
     -> return self.app(env, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
     -> return resp(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
     -> return resp(environ, start_response)
       /usr/lib/python2.7/dist-packages/routes/middleware.py(131)__call__()
     -> response = self.app(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
     -> return resp(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
     -> return resp(environ, start_response)
       /usr/lib/python2.7/dist-packages/routes/middleware.py(131)__call__()
     -> response = self.app(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
     -> return resp(environ, start_response)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
     -> resp = self.call_func(req, *args, **self.kwargs)
       /usr/local/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
     -> return self.func(req, *args, **kwargs)
       /opt/stack/neutron/neutron/api/v2/resource.py(87)resource()
     -> result = method(request=request, **args)
       /opt/stack/neutron/neutron/api/v2/base.py(328)show()
     -> parent_id=parent_id),
       /opt/stack/neutron/neutron/api/v2/base.py(283)_item()
     -> obj = obj_getter(request.context, id, **kwargs)
       /opt/stack/neutron/neutron/plugins/ml2/plugin.py(427)get_network()
     -> result = super(Ml2Plugin, self).get_network(context, id, None)
     > /opt/stack/neutron/neutron/db/db_base_plugin_v2.py(1032)get_network()
     -> network = self._get_network(context, id)
     (Pdb) 

/etc/neutron/api-paste.iniを見ると以下のように、authtokenとkeystonecontextが設定されている。
[composite:neutronapi_v2_0]のnoauthとkeystoneはneutron.confのauth_strategyに設定されている項目に対応すると考える::

     [composite:neutron]
     use = egg:Paste#urlmap
     /: neutronversions
     /v2.0: neutronapi_v2_0
     
     [composite:neutronapi_v2_0]
     use = call:neutron.auth:pipeline_factory
     noauth = request_id catch_errors extensions neutronapiapp_v2_0
     keystone = request_id catch_errors authtoken keystonecontext extensions neutronapiapp_v2_0
     
     [filter:request_id]
     paste.filter_factory = neutron.openstack.common.middleware.request_id:RequestIdMiddleware.factory
     
     [filter:catch_errors]
     paste.filter_factory = neutron.openstack.common.middleware.catch_errors:CatchErrorsMiddleware.factory
     
     [filter:keystonecontext]
     paste.filter_factory = neutron.auth:NeutronKeystoneContext.factory
     
     [filter:authtoken]
     paste.filter_factory = keystoneclient.middleware.auth_token:filter_factory
     
     [filter:extensions]
     paste.filter_factory = neutron.api.extensions:plugin_aware_extension_middleware_factory
     
     [app:neutronversions]
     paste.app_factory = neutron.api.versions:Versions.factory
     
     [app:neutronapiapp_v2_0]
     paste.app_factory = neutron.api.v2.router:APIRouter.factory
     

そこで、まずは、[filter:authtoken]のkeystoneclient.middleware.auth_tokenで実施されている処理を見てゆく。
なお、これは、上記スタックトレースで言う「★ココ！！」の部分に対応するものである。

auth_tokenの処理
----------------

tokenのvalidateを行う処理。

[ソース]
python-keystoneclient/keystoneclient/middleware/auth_token.py

[middleware architecture]
http://docs.openstack.org/developer/python-keystoneclient/middlewarearchitecture.html

以下が、auth_tokenで呼ばれるコードである(__call__が呼ばれる)。::

     class AuthProtocol(object):
         """Auth Middleware that handles authenticating client calls."""
     (snip)
         def __call__(self, env, start_response):
             """Handle incoming request.
     
             Authenticate send downstream on success. Reject request if
             we can't authenticate.
     
             """
             self.LOG.debug('Authenticating user token')
     
             self._token_cache.initialize(env)
     
             try:
                 self._remove_auth_headers(env)
                 user_token = self._get_user_token_from_header(env)
                 token_info = self._validate_user_token(user_token, env)
                 env['keystone.token_info'] = token_info
                 user_headers = self._build_user_headers(token_info)
                 self._add_headers(env, user_headers)
                 return self.app(env, start_response)
     
             except InvalidUserToken:
                 if self.delay_auth_decision:
                     self.LOG.info(
                         'Invalid user token - deferring reject downstream')
                     self._add_headers(env, {'X-Identity-Status': 'Invalid'})
                     return self.app(env, start_response)
                 else:
                     self.LOG.info('Invalid user token - rejecting request')
                     return self._reject_request(env, start_response)
     
             except ServiceError as e:
                 self.LOG.critical('Unable to obtain admin token: %s', e)
                 resp = MiniResp('Service unavailable', env)
                 start_response('503 Service Unavailable', resp.headers)
                 return resp.body
     (snip)
     
neutron.auth:NeutronKeystoneContextの処理
-------------------------------------------

user_id,tenant_id,roles,tenant_name,user_name,req_idをcontext.Contextクラスに詰め込んでreq.environ['neutron.context']に代入する。

[ソース]
neutron/auth.py

以下が、コードである。::

     class NeutronKeystoneContext(wsgi.Middleware):
         """Make a request context from keystone headers."""
     
         @webob.dec.wsgify
         def __call__(self, req):
             # Determine the user ID
             user_id = req.headers.get('X_USER_ID')
             if not user_id:
                 LOG.debug(_("X_USER_ID is not found in request"))
                 return webob.exc.HTTPUnauthorized()
     
             # Determine the tenant
             tenant_id = req.headers.get('X_PROJECT_ID')
     
             # Suck out the roles
             roles = [r.strip() for r in req.headers.get('X_ROLES', '').split(',')]
     
             # Human-friendly names
             tenant_name = req.headers.get('X_PROJECT_NAME')
             user_name = req.headers.get('X_USER_NAME')
     
             # Use request_id if already set
             req_id = req.environ.get(request_id.ENV_REQUEST_ID)
     
             # Create a context with the authentication data
             ctx = context.Context(user_id, tenant_id, roles=roles,
                                   user_name=user_name, tenant_name=tenant_name,
                                   request_id=req_id)
     
             # Inject the context...
             req.environ['neutron.context'] = ctx
     
             return self.application
     
     
     





認証の復習
----------

Authentication
認証
　ネットワークやサーバへ接続する際に本人性をチェックし、正規の利用者であることを確認する方法。一般には利用者IDとパスワードの組み合わせにより本人を特定する。認証がなされると、本人が持つ権限でデータへのアクセスやアプリケーションの利用が可能となる。不正利用を防ぐため、パスワードの漏えいなどには十分な注意が必要である。

http://www.atmarkit.co.jp/aig/02security/authentication.html

認可の復習
----------

Authorization
認可　

認証（Authentication）によって確認された利用者を識別して、アクセス権限の制御を行い、利用者ごとに固有のサービスを提供すること。

　具体的には、利用可能なアプリケーションの制御、ファイルに対する“読み／書き／実行”の権限など、利用者の資格に応じて許可する。認可のための属性情報には、利用者ID／所属グループ／役職／部署／アクセス制御リスト（ACL）などがある。

　運用管理の面から、認可はACL（Access Control List）で与えることがセキュリティ上でも望ましく、SSO（Single Sign On）でもACLと組み合わせることが多い。
http://www.atmarkit.co.jp/aig/02security/authorization.html


