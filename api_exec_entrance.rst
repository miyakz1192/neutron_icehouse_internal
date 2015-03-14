===============================
APIが実行される時の入り口
===============================

以下のようにトレースを設定してみた(ml2pluginのcreate_network)。::

    def create_network(self, context, network):
        import pdb
        pdb.set_trace()


そうすると、以下のようなトレースが出てきた。::

  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(368)create_network()
  -> net_data = network['network']
  (Pdb) bt
    /usr/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
  -> func(*args, **kwargs)
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(584)process_request()
  -> proto.__init__(socket, address, self)
    /usr/lib/python2.7/SocketServer.py(649)__init__()
  -> self.handle()
    /usr/lib/python2.7/BaseHTTPServer.py(340)handle()
  -> self.handle_one_request()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(280)handle_one_request()
  -> self.handle_one_response()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(384)handle_one_response()
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
    /opt/stack/neutron/neutron/api/v2/base.py(448)create()
  -> obj = obj_creator(request.context, **kwargs)
  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(368)create_network()
  -> net_data = network['network']
  (Pdb) 
  
"/opt/stack/neutron/neutron/api/v2/base.py(448)create()"が鍵になるらしい。::


    def resource(request):
    (snip)
        try:
            if request.body:
                args['body'] = deserializer.deserialize(request.body)['body']

            method = getattr(controller, action)

            result = method(request=request, **args)
        except (exceptions.NeutronException,
    (snip)

要するに、request.urlとargsをダンプして、resultも同様にやればいいかな。

