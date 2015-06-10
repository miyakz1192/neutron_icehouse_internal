=========================
portのintegrity check
=========================

create_port時にportのnetwork_idを不正なものに変更する。
DBへのsave時にエラーになる。::

      (Pdb) p port
      <neutron.db.models_v2.Port[object at 421f1d0] {tenant_id=u'bbf770e7cc7d499fba61abc002be7693', id='bf765822-7c37-449a-bf78-921aa5ff4466', name=u'test3', network_id='xxx', mac_address='fa:16:3e:7c:9d:17', admin_state_up=True, status='DOWN', device_id='', device_owner=''}>
      (Pdb) c
      2014-10-11 16:38:00.980 ERROR neutron.api.v2.resource [-] create failed
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource Traceback (most recent call last):
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/opt/stack/neutron/neutron/api/v2/resource.py", line 87, in resource
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     result = method(request=request, **args)
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/opt/stack/neutron/neutron/api/v2/base.py", line 453, in create
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     obj = obj_creator(request.context, **kwargs)
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/opt/stack/neutron/neutron/plugins/ml2/plugin.py", line 643, in create_port
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     result = super(Ml2Plugin, self).create_port(context, port)
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/opt/stack/neutron/neutron/db/db_base_plugin_v2.py", line 1406, in create_port
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     port_id=port_id,
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/usr/local/lib/python2.7/dist-packages/sqlalchemy/orm/session.py", line 463, in __exit__
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     self.rollback()
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/usr/local/lib/python2.7/dist-packages/sqlalchemy/util/langhelpers.py", line 57, in __exit__
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     compat.reraise(exc_type, exc_value, exc_tb)
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/usr/local/lib/python2.7/dist-packages/sqlalchemy/orm/session.py", line 460, in __exit__
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     self.commit()
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/usr/local/lib/python2.7/dist-packages/sqlalchemy/orm/session.py", line 370, in commit
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     self._prepare_impl()
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/usr/local/lib/python2.7/dist-packages/sqlalchemy/orm/session.py", line 350, in _prepare_impl
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     self.session.flush()
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource   File "/opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py", line 458, in _wrap
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource     raise exception.DBError(e)
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource DBError: (IntegrityError) (1452, 'Cannot add or update a child row: a foreign key constraint fails (`neutron_ml2`.`ports`, CONSTRAINT `ports_ibfk_1` FOREIGN KEY (`network_id`) REFERENCES `networks` (`id`))') 'INSERT INTO ports (tenant_id, id, name, network_id, mac_address, admin_state_up, status, device_id, device_owner) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)' ('bbf770e7cc7d499fba61abc002be7693', 'bf765822-7c37-449a-bf78-921aa5ff4466', 'test3', 'xxx', 'fa:16:3e:7c:9d:17', 1, 'DOWN', '', '')
      2014-10-11 16:38:00.980 TRACE neutron.api.v2.resource 	

ちなみにmysqlから変更しようとした場合もエラーになる。::

      mysql> update ports set network_id="xxxxxx" where id="f0ff6745-82d8-4150-8a85-6a3ea1777a68" 
          -> ;
      ERROR 1452 (23000): Cannot add or update a child row: a foreign key constraint fails (`neutron_ml2`.`ports`, CONSTRAINT `ports_ibfk_1` FOREIGN KEY (`network_id`) REFERENCES `networks` (`id`))
      mysql> ^CCtrl-C -- exit!
      

DBがマルチマスタでreplicationされた場合にどうなるんだろうな
