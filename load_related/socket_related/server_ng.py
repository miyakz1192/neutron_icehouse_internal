#!/usr/bin/env python 

""" 
A simple echo server 
""" 

import socket 
import time

host = '' 
port = 1192
backlog = 5 
size = 1024 
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
s.bind((host,port)) 
s.listen(backlog) 
while 1: 
    client, address = s.accept() 
    print "send data 1"
    client.send("1234567890") 
    print "sleep 5"
    time.sleep(5)
    print "send data 2"
    client.send("1234567890") 
    client.close()
