=======================================================
高負荷関連のメモ
=======================================================

どういう流れで、web serverが実行されているのか観点での
調査のメモ::

  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(443)handle_one_response()
  -> 'request_line': self.requestline,
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(444)handle_one_response()
  -> 'status_code': status_code[0],
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(445)handle_one_response()
  -> 'body_length': length[0],
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(446)handle_one_response()
  -> 'wall_seconds': finish - start,
  (Pdb) 
  2015-12-12 16:23:39.195 24292 INFO neutron.wsgi [req-5cdc4b35-205a-43aa-b293-287b2b4ecf67 None] 192.168.122.84 - - [12/Dec/2015 16:23:39] "GET /v2.0/networks.json HTTP/1.1" 200 2602 37.887409
  
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(446)handle_one_response()->None
  -> 'wall_seconds': finish - start,
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(286)handle_one_request()
  -> self.server.outstanding_requests -= 1
  (Pdb) 
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(286)handle_one_request()->None
  -> self.server.outstanding_requests -= 1
  (Pdb) 
  > /usr/lib/python2.7/BaseHTTPServer.py(341)handle()
  -> while not self.close_connection:
  (Pdb) 
  > /usr/lib/python2.7/BaseHTTPServer.py(342)handle()
  -> self.handle_one_request()
  (Pdb) 
  
正体は以下。
/usr/lib/python2.7/dist-packages/eventlet/wsgi.py
コードは以下。::

  197 class HttpProtocol(BaseHTTPServer.BaseHTTPRequestHandler):                      
  198     protocol_version = 'HTTP/1.1'                                               
  199     minimum_chunk_size = MINIMUM_CHUNK_SIZE   
  (snip)
  438             if self.server.log_output:                                          
  439                 self.server.log_message(self.server.log_format % {              
  440                     'client_ip': self.get_client_ip(),                          
  441                     'client_port': self.client_address[1],                      
  442                     'date_time': self.log_date_time_string(),                   
  443                     'request_line': self.requestline,                           
  444                     'status_code': status_code[0],                              
  445                     'body_length': length[0],                                   
  446                     'wall_seconds': finish - start,                             
  447                 })  
  (snip)
  667         serv.log.write("(%s) wsgi starting up on %s://%s%s/\n" % ( 
  668             serv.pid, scheme, host, port))   

handle_one_responseメソッドでログが吐き出されている。
あと、eventlet/hub.pyにてtaskletの切り替えが行われている。
多分、eventlet/hub.pyにてtaskletの切り替えが行われ、handle_one_request -> handle_one_responseと
処理が進んでいる。したがって、handle_one_responseで生成したuuidをcreate_portまで伝達できれば、
一貫した印を持ってログを記録できるはずだ。

以下、eventletのwsgiから、そこ上で動作するアプリケーションに渡される情報の経路
を追った。::

  > /usr/lib/python2.7/dist-packages/paste/urlmap.py(205)__call__()
  -> environ['PATH_INFO'] = path_info[len(app_url):]
  (Pdb) *** NameError: name 'ln' is not defined
  (Pdb) l*** NameError: name 'ln' is not defined
  (Pdb) l
  *** NameError: name 'll' is not defined
  (Pdb) l
  200               if domain and domain != host and domain != host+':'+port:
  201                   continue
  202               if (path_info == app_url
  203                   or path_info.startswith(app_url + '/')):
  204                   environ['SCRIPT_NAME'] += app_url
  205  ->                 environ['PATH_INFO'] = path_info[len(app_url):]
  206                   return app(environ, start_response)
  207           environ['paste.urlmap_object'] = self
  208           return self.not_found_application(environ, start_response)
  209   
  210   
  (Pdb) 

create_portのところまでのbtをみることで、wsgiで設定した情報が伝搬できないか
を確認。::

  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
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
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(392)handle_one_response()
  -> self.environ['uuid'] = uuid_str
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
  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) 

environは以下、dec.py(144)同ファイルの130の処理に至るところで変換（抽象化）
されている::

  (Pdb) u
  > /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
  (Pdb) l
  139                   body = resp
  140                   resp = req.response
  141                   resp.write(body)
  142               if resp is not req.response:
  143                   resp = req.response.merge_cookies(resp)
  144  ->             return resp(environ, start_response)
  145           else:
  146               if self.middleware_wraps:
  147                   args = (self.middleware_wraps,) + args
  148               return self.func(req, *args, **kw)
  149   
  (Pdb) 

environがcreate_portに至る頃には、reqに変換されているようだ::

  > /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
  (Pdb) l
  125               req.response = req.ResponseClass()
  126               try:
  127                   args = self.args
  128                   if self.middleware_wraps:
  129                       args = (self.middleware_wraps,) + args
  130  ->                 resp = self.call_func(req, *args, **self.kwargs)
  131               except HTTPException as exc:
  132                   resp = exc
  133               if resp is None:
  134                   ## FIXME: I'm not sure what this should be?
  135                   resp = req.response
  (Pdb) 

キモは同ファイルの以下の行で行われる処理らしい::

  124             req = self.RequestClass(environ)                                                                                                      
"/opt/stack/neutron/neutron/api/v2/base.py(448)create()"
のcreate_portからは以下のように参照できる::

  request.environ

handle_one_responseで生成したUUIDは以下の通り参照できる。::

  (Pdb) p request.environ["uuid"]
  UUID('1d30f7ad-2470-49b2-99e3-06a1801384d9')
  (Pdb) 

wsgi.pyのhandle_one_responseでは以下のようにuuidを入れ込んでいる。::

  387         try:                                                                    
  388             try:                                                                
  389                 uuid_str = uuid.uuid4()                                         
  390 #                import pdb                                                     
  391 #                pdb.set_trace()
  392                 self.environ['uuid'] = uuid_str★ココがポイント
  393                 if self.server.log_output:                                      
  394                     self.server.log_message(DEFAULT_LOG_FORMAT_START % {        
  395                         'client_ip': self.get_client_ip(),                      
  396                         'client_port': self.client_address[1],                  
  397                         'date_time': self.log_date_time_string(),               
  398                         'request_line': self.requestline,                       
  399                         'uuid':         uuid_str                                
  400                     })           

肝心のML2Pluginのcreate_portからはどうやって参照するのか？
結局以下のように、
"/opt/stack/neutron/neutron/api/v2/base.py(448)create()"
で、"request"のcontextのみ渡されているので、肝心の情報をもらうことができない。
ってことで、neutron.context.Contextを拡張してやる。


試しにapi_worker=2,rpc_worker=2で多重実行してみる
===================================================

port-createを多重で実行するテストプログラム::

  net = "bf285ec8-0e33-4482-b1a9-82a7526c11c2"
  count_max=1
  parallel_max=50
  
  for count in 1..count_max do 
    threads = []
    for parallel in 1..parallel_max do
      t = Thread.start(parallel) do |_parallel|
        Thread.pass
        puts "neutron port-create --name port#{_parallel} #{net}"
        `neutron port-create --name port#{_parallel} #{net}`
        sleep 1
        puts "neutron port-delete port#{_parallel}"
        `neutron port-delete port#{_parallel}`
      end
      threads << t
    end 
    threads.each do |t|
      t.join
    end
  end

port-createにかかった時間をログから求めるスクリプト::
  grep neutron.wsgi  /tmp/res | grep -v REQ | grep POST | awk '{print $18}'  | sort -n 

多重度50で実行すると、34secかかったport-createが存在した。
CPU数が1だからか。。。workerが2なので、CPU数を4にしてみる。
もう一度同じスクリプトを実行してみると、11secかかった、port-createが存在した。

1workerあたり1000スレッドということを考えると、性能が悪すぎる。どこで
性能が悪くなっているかを解析する。

と思ったが、50並列だとNSのload averageが10以上と重たくなるので、25並列にした。
この場合だと行って7程度。ちょっと、VM(all in one)の中で、負荷試験ツールを
動作させると、neutron-serverとツールが起動するneutronコマンドの間で、
CPUの喰い合いが発生するため、適切ではない。よって、負荷試験ツールを
別のマシン(neutron-server VMが動作しているVMホスト)で動作させることにする。

別のマシンで動作させることにより、負荷テスト時のneutron-serverの動作VMの
load averageが4未満になった。この時のport-createの最大処理時間は、1.8secであった。
もうちょっと並列度を上げてみて、100で行ってみる。100だとVMホストのload averageが
60を超えるという異常事態になったので、60で行ってみる。
60だとVMホストのload averageが10、neutron-serverのload averageが4ちょっと。
最小処理時間が0.03sec。最大処理時間が1.7secなので、このデータで分析してみる。

最大時間が1.7secとなった回では、以下のように、DEBUG12とDEBUG13の間で約1secかかっている::

  2015-12-14 16:32:26.784 14826 INFO neutron.plugins.ml2.plugin [req-ba052180-0f59-42b6-b100-2ff41caae496 None] [DEBUG12] 6c45ed57-5874-4934-ba2a-357c7e9ebf6d
  2015-12-14 16:32:27.885 14826 INFO neutron.plugins.ml2.plugin [req-ba052180-0f59-42b6-b100-2ff41caae496 None] [DEBUG13] 6c45ed57-5874-4934-ba2a-357c7e9ebf6d


しかし、両区間にはCPU時間を消費する処理はなにもない。::
  

  662             LOG.info(_("[DEBUG12] %(uuid)s")%{'uuid': uuid_stamp})              
  663             self.mechanism_manager.create_port_precommit(mech_context)          
  664                                                                                 
  665         try:                                                                    
  666             self.mechanism_manager.create_port_postcommit(mech_context)         
  667             LOG.info(_("[DEBUG13] %(uuid)s")%{'uuid': uuid_stamp})   

実験中はneutron-serverのload averageは4近くだったことから、単に高負荷であったため
だと考える。

70多重
-------

今度は負荷テストプログラム側の多重度を70にしてみる。

==============    =========
load average
---------------------------
ツール側           NS側
==============    =========
14                4
==============    =========
  
結果。

==============    =========
port-create処理時間
---------------------------
最小              最大        平均
==============    =========   =========
0.241192          3.247623    0.8479923714285711
==============    =========   =========

3.2secかかった区間を分析してみる::

  miyakz@icehouse01:~$ grep 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37 /tmp/res
  2015-12-14 16:52:02.017 18919 INFO neutron.wsgi [req-8e6650ee-29cf-425b-a7be-7602e26b5cfc None] WSGI_REQ_START: 192.168.122.1 - - [14/Dec/2015 16:52:02] "POST /v2.0/ports.json HTTP/1.1" 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.232 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG1] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.233 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG2] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.267 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG3] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.295 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG4] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.295 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG5] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.367 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG6] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.370 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG7] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.387 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG8] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.395 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG9] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.396 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG10] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.397 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG11] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.398 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG12] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.573 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG13] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.582 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG14] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.624 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG15] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:05.264 18919 INFO neutron.wsgi [req-6fcd80eb-9cb1-444b-90a3-05f4fb3cab1b None] WSGI_REQ_END 192.168.122.1 - - [14/Dec/2015 16:52:05] "POST /v2.0/ports.json HTTP/1.1" 201 753 3.247623 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  miyakz@icehouse01:~$ 

DEBUG15が終わったあと、WSGI_REQ_ENDを出力するまでに時間がかかっている。::

  675         LOG.info(_("[DEBUG15] %(uuid)s")%{'uuid': uuid_stamp})                  
  676         return result 
  
DEBUG15のあとはresultを返すだけなので、問題ない。どこかの経路で
3sec消費しているところがあるはずだ。仮説としては、sleepまたは、
IO処理などで、eventletのタスク切り替えが発生したか。

create_portのところまでのbtを丁寧に追ってみる::

  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
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
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(392)handle_one_response()
  -> self.environ['uuid'] = uuid_str

     handle_one_responseで最終的にログを出力するのは以下の箇所
     create_portからここに至るまでに経路を追う。
     455             if self.server.log_output:                                          
     456                 self.server.log_message(self.server.log_format % {              
     457                     'client_ip': self.get_client_ip(),                          
     458                     'client_port': self.client_address[1],                      
     459                     'date_time': self.log_date_time_string(),                   
     460                     'request_line': self.requestline,                           
     461                     'status_code': status_code[0],                              
     462                     'body_length': length[0],                                   
     463                     'wall_seconds': finish - start,                             
     464                     'uuid':         uuid_str                                    
     465                 })      


    /usr/lib/python2.7/dist-packages/paste/urlmap.py(206)__call__()
  -> return app(environ, start_response)

     上位appを呼び出して即座に復帰する。他の処理が入り込む余地は無い。
     206                 return app(environ, start_response)

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
     
     call_funcでおそらくcreate_portを呼び出して、144でrespを呼び出す。respの正体は謎(TODO: check)
     130                 resp = self.call_func(req, *args, **self.kwargs)                
     131             except HTTPException as exc:                                        
     132                 resp = exc                                                      
     133             if resp is None:                                                    
     134                 ## FIXME: I'm not sure what this should be?                     
     135                 resp = req.response                                             
     136             if isinstance(resp, text_type):                                     
     137                 resp = bytes_(resp, req.charset) ★ここはエンコーディングをしているだけ(時間がかかる要素ではある) 
     138             if isinstance(resp, bytes):                                         
     139                 body = resp                                                     
     140                 resp = req.response                                             
     141                 resp.write(body)                                                
     142             if resp is not req.response:                                        
     143                 resp = req.response.merge_cookies(resp)                         
     144             return resp(environ, start_response)   

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
     
     funcを呼び出して即復帰
     192     def call_func(self, req, *args, **kwargs):                                  
     193         """Call the wrapped function; override this in a subclass to            
     194         change how the function is called."""                                   
     195         return self.func(req, *args, **kwargs)    

    /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
  -> response = req.get_response(self.application)

     create_portを呼び出したあと、そのresponseデータにヘッダを付け加えているだけ。
     32 class RequestIdMiddleware(base.Middleware):                                     
     33                                                                                 
     34     @webob.dec.wsgify                                                           
     35     def __call__(self, req):                                                    
     36         req_id = context.generate_request_id()                                  
     37         req.environ[ENV_REQUEST_ID] = req_id                                    
     38         response = req.get_response(self.application)                           
     39         if HTTP_RESP_HEADER_REQUEST_ID not in response.headers:                 
     40             response.headers.add(HTTP_RESP_HEADER_REQUEST_ID, req_id)           
     41         return response      
    
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)

     create_portを呼び出して、その結果をResponseClassにして返却しているだけ。
     たぶん、request.Responseだと思う(TODO: check)。
     1300     def send(self, application=None, catch_exc_info=False):                     
     1301         """                                                                     
     1302         Like ``.call_application(application)``, except returns a               
     1303         response object with ``.status``, ``.headers``, and ``.body``           
     1304         attributes.                                                             
     1305                                                                                 
     1306         This will use ``self.ResponseClass`` to figure out the class            
     1307         of the response object to return.                                       
     1308                                                                                 
     1309         If ``application`` is not given, this will send the request to          
     1310         ``self.make_default_send_app()``                                        
     1311         """                                                                     
     1312         if application is None:                                                 
     1313             application = self.make_default_send_app()                          
     1314         if catch_exc_info:                                                      
     1315             status, headers, app_iter, exc_info = self.call_application(        
     1316                 application, catch_exc_info=True)                               
     1317             del exc_info                                                        
     1318         else:                                                                   
     1319             status, headers, app_iter = self.call_application(                  
     1320                 application, catch_exc_info=False)                              
     1321         return self.ResponseClass(                                              
     1322             status=status, headerlist=list(headers), app_iter=app_iter) 


    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)


     create_portを呼び出して、その結果をoutputに代入して、返しているだけ。
     closeが呼び出される場合がある？？謎(TODO: check)
      1284         app_iter = application(self.environ, start_response)                    
      1285         if output or not captured:                                              
      1286             try:                                                                
      1287                 output.extend(app_iter)                                         
      1288             finally:                                                            
      1289                 if hasattr(app_iter, 'close'):                                  
      1290                     app_iter.close()                                            
      1291             app_iter = output                                                   
      1292         if catch_exc_info:                                                      
      1293             return (captured[0], captured[1], app_iter, captured[2])            
      1294         else:                                                                   
      1295             return (captured[0], captured[1], app_iter)  

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)

     →　上述の通り

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)

     create_portを呼び出して即時復帰するだけ。
     192     def call_func(self, req, *args, **kwargs):                                  
     193         """Call the wrapped function; override this in a subclass to            
     194         change how the function is called."""                                   
     195         return self.func(req, *args, **kwargs)  

    /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
  -> response = req.get_response(self.application)

     create_port呼び出しをくるむだけ::
     33 class CatchErrorsMiddleware(base.Middleware):                                   
     34                                                                                 
     35     @webob.dec.wsgify                                                           
     36     def __call__(self, req):                                                    
     37         try:                                                                    
     38             response = req.get_response(self.application)                       
     39         except Exception:                                                       
     40             LOG.exception(_LE('An error occurred during '                       
     41                               'processing the request: %s'))                    
     42             response = webob.exc.HTTPInternalServerError()                      
     43         return response  

    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)

     →　上述の通り

    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)

     →　上述の通り

    /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py(687)__call__()
  -> return self.app(env, start_response)

    create_portを呼び出したあとは即時復帰::
 
    680         try:                                                                    
    681             self._remove_auth_headers(env)                                      
    682             user_token = self._get_user_token_from_header(env)                  
    683             token_info = self._validate_user_token(user_token, env)             
    684             env['keystone.token_info'] = token_info                             
    685             user_headers = self._build_user_headers(token_info)                 
    686             self._add_headers(env, user_headers)                                
    687             return self.app(env, start_response)     

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

  　即座に復帰するのみ
   144             return resp(environ, start_response) 

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。

    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)

   create_portを呼び出してちょっとしたハッシュの処理をやってから、復帰
   136         response = self.app(environ, start_response) 
   137                                                                                 
   138         # Wrapped in try as in rare cases the attribute will be gone already    
   139         try:                                                                    
   140             del self.mapper.environ                                             
   141         except AttributeError:                                                  
   142             pass                                                                
   143         return response    

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。
    
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。
    
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)

    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
  
    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)

    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)

    →　上述の通り。

    /opt/stack/neutron/neutron/api/v2/resource.py(87)resource()
  -> result = method(request=request, **args)

   resultをシリアライズする処理で時間がかかるかも(TODO: check)
   87             result = method(request=request, **args)★ここでresultを得る
   (snip)
   138         status = action_status.get(action, 200)                                 
   139         body = serializer.serialize(result)   ★　ここで何やらシリアライズをする（時間がかかるかも)
   140         # NOTE(jkoelker) Comply with RFC2616 section 9.7                        
   141         if status == 204:                                                       
   142             content_type = ''                                                   
   143             body = None                                                         
   144                                                                                 
   145         return webob.Response(request=request, status=status,                   
   146                               content_type=content_type,                        
   147                               body=body)   


    /opt/stack/neutron/neutron/api/v2/base.py(448)create()
  -> obj = obj_creator(request.context, **kwargs)

   439         else:                                                                   
   440             obj_creator = getattr(self._plugin, action)                         
   441             if self._collection in body:                                        
   442                 # Emulate atomic bulk behavior                                  
   443                 objs = self._emulate_bulk_create(obj_creator, request,          
   444                                                  body, parent_id)               
   445                 return notify({self._collection: objs})                         
   446             else:                                                               
   447                 kwargs.update({self._resource: body})                           
   448                 request.context.logstamp = request.environ["uuid"]              
   449                 obj = obj_creator(request.context, **kwargs) ★　今回はココ                   
   450                                                                                 
   451                 self._nova_notifier.send_network_change( ★　computeの portの場合はこの処理の延長でeventlet.sleep ①                      
   452                     action, {}, {self._resource: obj})                          
   453                 return notify({self._resource: self._view( ★  computeじゃなくても、この延長で通信するのでsleep ②
   454                     request.context, obj)})    


  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) 

computeのportの場合はeventlet.sleepが走る　①
DHCP agentにportの追加を通知するところでIOが発生するので、そこで、
eventletの切り替えが走る ②

結論としては、create_portの最後でDHCP agentに通知をするところでIOが走るため②、
ここで、時間を喰うことがある。

[memo]今回、復帰時で遅延が見られたが、create_port呼び出し時で
遅延が発生した場合には、keystoneのvalidationのところで、eventlet
切り替えが発生して遅延したのかもしれない。


