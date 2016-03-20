==========================================================
neutron-serverの障害分析に使えるログの強化など　
==========================================================

ログ強化の対象
===============

1. 性能
2. シーケンス

性能
----

neutron-serverが使っているeventletにより、性能が安定しにくいことは周知の通り。
性能劣化現象が発生した時に、容易に切り分けが可能なように、ログを強化する。

neutron-serverがREST-API のリクエストを受け取ってからそれが終了するまでにrequest-idが
付与される。それが受付時にはまだ判明していないこと、agentに対してRPCを送るときも
不明(?要調査)。

REST API受信のシーケンス
--------------------------

大まかには以下::

  eventlet.wsgi -> paste deployment -> neutron-serverのプラグイン、サービスのメソッド



性能ログ強化
===============

ログ::

  (Pdb) bt
    /usr/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
  -> func(*args, **kwargs)
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(602)process_request()
  -> proto.__init__(socket, address, self)
    /usr/lib/python2.7/SocketServer.py(649)__init__()
  -> self.handle()
    /usr/lib/python2.7/BaseHTTPServer.py(342)handle()
  -> self.handle_one_request()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(285)handle_one_request()
  -> self.handle_one_response()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(401)handle_one_response()
  -> result = self.application(self.environ, start_response)
    /usr/lib/python2.7/dist-packages/paste/urlmap.py(206)__call__()
  -> return app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
  -> response = req.get_response(self.application)
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)
    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
  -> response = req.get_response(self.application)
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)
    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)
    /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py(687)__call__()
  -> return self.app(env, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/api/v2/resource.py(87)resource()
  -> result = method(request=request, **args)
    /opt/stack/neutron/neutron/api/v2/base.py(449)create()
  -> obj = obj_creator(request.context, **kwargs)
    /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  > /usr/lib/python2.7/logging/__init__.py(1427)info()
  -> def info(self, msg, *args, **kwargs):
  (Pdb) 2015-12

  (Pdb) a
  self = <neutron.openstack.common.log.ContextAdapter object at 0x7fe916bcadd0>
  msg = [DEBUG1] ef82166c-3375-4cf7-88ba-2a5135dbed97
  args = ()
  kwargs = {}
  (Pdb) 

  (Pdb) s
  --Call--
  > /opt/stack/neutron/neutron/openstack/common/log.py(308)process()
  -> def process(self, msg, kwargs):
  (Pdb) l
  303               self.critical(stdmsg, *args, **kwargs)
  304               raise DeprecatedConfig(msg=stdmsg)
  305           else:
  306               self.warn(stdmsg, *args, **kwargs)
  307   
  308  ->     def process(self, msg, kwargs):
  309           # NOTE(mrodden): catch any Message/other object and
  310           #                coerce to unicode before they can get
  311           #                to the python logging and possibly
  312           #                cause string encoding trouble
  313           if not isinstance(msg, six.string_types):
  (Pdb) n
  > /opt/stack/neutron/neutron/openstack/common/log.py(313)process()
  -> if not isinstance(msg, six.string_types):
  (Pdb) l
  308       def process(self, msg, kwargs):
  309           # NOTE(mrodden): catch any Message/other object and
  310           #                coerce to unicode before they can get
  311           #                to the python logging and possibly
  312           #                cause string encoding trouble
  313  ->         if not isinstance(msg, six.string_types):
  314               msg = six.text_type(msg)
  315   
  316           if 'extra' not in kwargs:
  317               kwargs['extra'] = {}
  318           extra = kwargs['extra']
  (Pdb) 

log出力時につけるプロセスIDは、ローカルスレッドストレージに保存
されたストレージから取得される。::

  (Pdb) n
  > /opt/stack/neutron/neutron/openstack/common/log.py(323)process()
  -> if context:
  (Pdb) l
  318           extra = kwargs['extra']
  319   
  320           context = kwargs.pop('context', None)
  321           if not context:
  322               context = getattr(local.store, 'context', None)
  323  ->         if context:
  324               extra.update(_dictify_context(context))
  325   
  326           instance = kwargs.pop('instance', None)
  327           instance_uuid = (extra.get('instance_uuid', None) or
  328                            kwargs.pop('instance_uuid', None))
  (Pdb) 

thread idは以下::


  (Pdb) l
  628           attrs['status'] = const.PORT_STATUS_DOWN
  629           #uuid_stamp = uuid.uuid4()
  630           uuid_stamp = context.logstamp
  631           import pdb
  632           pdb.set_trace()
  633  ->         LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  634   
  635           session = context.session
  636           with session.begin(subtransactions=True):
  637               LOG.info(_("[DEBUG2] %(uuid)s")%{'uuid': uuid_stamp})
  638               self._ensure_default_security_group_on_port(context, port)
  (Pdb) inspect.getmembers(greenthread.getcurrent())
  [('GreenletExit', <class 'greenlet.GreenletExit'>), ('__class__', <type 'greenlet.greenlet'>), ('__delattr__', <method-wrapper '__delattr__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__dict__', {}), ('__doc__', 'greenlet(run=None, parent=None) -> greenlet\n\nCreates a new greenlet object (without running it).\n\n - *run* -- The callable to invoke.\n - *parent* -- The parent greenlet. The default is the current greenlet.'), ('__format__', <built-in method __format__ of greenlet.greenlet object at 0x7f411bb027d0>), ('__getattribute__', <method-wrapper '__getattribute__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__getstate__', <built-in method __getstate__ of greenlet.greenlet object at 0x7f411bb027d0>), ('__hash__', <method-wrapper '__hash__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__init__', <method-wrapper '__init__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__new__', <built-in method __new__ of type object at 0x7f4125a00a60>), ('__nonzero__', <method-wrapper '__nonzero__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__reduce__', <built-in method __reduce__ of greenlet.greenlet object at 0x7f411bb027d0>), ('__reduce_ex__', <built-in method __reduce_ex__ of greenlet.greenlet object at 0x7f411bb027d0>), ('__repr__', <method-wrapper '__repr__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__setattr__', <method-wrapper '__setattr__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__sizeof__', <built-in method __sizeof__ of greenlet.greenlet object at 0x7f411bb027d0>), ('__str__', <method-wrapper '__str__' of greenlet.greenlet object at 0x7f411bb027d0>), ('__subclasshook__', <built-in method __subclasshook__ of type object at 0x7f4125a00a60>), ('dead', False), ('error', <class 'greenlet.error'>), ('getcurrent', <built-in function getcurrent>), ('gettrace', <built-in function gettrace>), ('gr_frame', None), ('parent', <greenlet.greenlet object at 0x7f4122364d70>), ('settrace', <built-in function settrace>), ('switch', <built-in method switch of greenlet.greenlet object at 0x7f411bb027d0>), ('throw', <built-in method throw of greenlet.greenlet object at 0x7f411bb027d0>)]
  (Pdb) 

どうも、greenthreadにはIDというものはないらしい。せいぜい、pythonの
IDくらいか？::
  
  (Pdb) greenthread.getcurrent()
  <greenlet.greenlet object at 0x7f411bb027d0>
  (Pdb) 

  (Pdb) id(greenthread.getcurrent())
  139917614131152
  (Pdb) 


ちょっとバグっている
=====================

コンテキスト切り替えが発生すると、request_uuidが失われてしまう？::

  2016-01-04 17:42:55.985 17921 INFO neutron.plugins.ml2.plugin [6ad2385d-7108-4745-b561-dc4c3d2343a1 None] [DEBUG14] 6ad2385d-7108-4745-b561-dc4c3d2343a1
  2016-01-04 17:42:55.985 17921 DEBUG neutron.openstack.common.rpc.amqp [6ad2385d-7108-4745-b561-dc4c3d2343a1 None] Making asynchronous fanout cast... fanout_cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:599
  2016-01-04 17:42:55.986 17921 DEBUG neutron.openstack.common.rpc.amqp [6ad2385d-7108-4745-b561-dc4c3d2343a1 None] UNIQUE_ID is 9d58e415beef4c5188d43fea4ca862de. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:343
  2016-01-04 17:42:55.987 17921 DEBUG neutron.context [req-74f3214d-f879-46f2-ad4e-800bc9bae51b None] Arguments dropped when creating context: {'project_name': None, 'tenant': None} __init__ /opt/stack/neutron/neutron/context.py:96
  2016-01-04 17:42:55.987 17921 DEBUG neutron.plugins.ml2.db [req-74f3214d-f879-46f2-ad4e-800bc9bae51b None] get_port_and_sgs() called for port_id 14ee9ef6-97b0-4ad0-b9e9-79a82647351e get_port_and_sgs /opt/stack/neutron/neutron/plugins/ml2/db.py:100
  2016-01-04 17:42:56.008 17921 INFO neutron.plugins.ml2.plugin [-] [DEBUG15] 6ad2385d-7108-4745-b561-dc4c3d2343a1
  2016-01-04 17:42:56.009 17921 DEBUG neutron.openstack.common.rpc.amqp [-] Sending port.create.end on notifications.info notify /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:629

第２例::

  2016-01-04 17:43:01.161 17921 INFO neutron.plugins.ml2.plugin [cd4cbaa5-b4e6-4c8c-b7b4-56dc8ce83f49 None] [DEBUG14] cd4cbaa5-b4e6-4c8c-b7b4-56dc8ce83f49
  2016-01-04 17:43:01.162 17921 DEBUG neutron.openstack.common.rpc.amqp [cd4cbaa5-b4e6-4c8c-b7b4-56dc8ce83f49 None] Making asynchronous fanout cast... fanout_cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:599
  2016-01-04 17:43:01.162 17921 DEBUG neutron.openstack.common.rpc.amqp [cd4cbaa5-b4e6-4c8c-b7b4-56dc8ce83f49 None] UNIQUE_ID is ad8420011f654d1485667106ed9203a4. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:343
  2016-01-04 17:43:01.165 17921 INFO neutron.wsgi [-] WSGI_REQ_START: 192.168.122.1 - - [04/Jan/2016 17:43:01] "GET /v2.0/networks.json?fields=id&id=bf285ec8-0e33-4482-b1a9-82a7526c11c2 HTTP/1.1" 85371fad-5af8-4556-92e6-263e752281cc
  
  2016-01-04 17:43:01.166 17921 DEBUG keystoneclient.middleware.auth_token [-] Authenticating user token __call__ /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:676
  2016-01-04 17:43:01.166 17921 DEBUG keystoneclient.middleware.auth_token [-] Removing headers from request environment: X-Identity-Status,X-Domain-Id,X-Domain-Name,X-Project-Id,X-Project-Name,X-Project-Domain-Id,X-Project-Domain-Name,X-User-Id,X-User-Name,X-User-Domain-Id,X-User-Domain-Name,X-Roles,X-Service-Catalog,X-User,X-Tenant-Id,X-Tenant-Name,X-Tenant,X-Role _remove_auth_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:733
  2016-01-04 17:43:01.175 17921 DEBUG neutron.context [req-74f3214d-f879-46f2-ad4e-800bc9bae51b None] Arguments dropped when creating context: {'project_name': None, 'tenant': None} __init__ /opt/stack/neutron/neutron/context.py:96
  2016-01-04 17:43:01.176 17921 DEBUG neutron.plugins.ml2.db [req-74f3214d-f879-46f2-ad4e-800bc9bae51b None] get_port_and_sgs() called for port_id 14ee9ef6-97b0-4ad0-b9e9-79a82647351e get_port_and_sgs /opt/stack/neutron/neutron/plugins/ml2/db.py:100
  2016-01-04 17:43:01.223 17921 INFO neutron.plugins.ml2.plugin [-] [DEBUG15] cd4cbaa5-b4e6-4c8c-b7b4-56dc8ce83f49




