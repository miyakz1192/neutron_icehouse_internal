#!/usr/bin/env python 

""" 
A simple echo server 
""" 

import socket 

host = '' 
port = 1192
backlog = 5 
size = 1024 
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
s.bind((host,port)) 
s.listen(backlog) 
while 1: 
    client, address = s.accept() 
    client.send("1234567890") 
    client.close()
