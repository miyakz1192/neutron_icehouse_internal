#include <sys/fcntl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>


#define ERROR(x) {\
                  fprintf(stderr, "client - ");\
                  perror(x);\
                  exit(1);\
                 }

int main(int argc, char **argv)
{

    int sockfd, len, result;
    struct sockaddr_in address;
    char ch[128];
    int read_len = 0 ;

    /*クライアント用ソケット作成*/
    sockfd = socket(AF_INET, SOCK_STREAM, 0);

    /*サーバ側と同じ名前でソケットの名前を指定*/
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    address.sin_port = htons(1192);
    len = sizeof(address);

    /*クライアントのソケットとサーバのソケットの接続*/
    result = connect(sockfd, (struct sockaddr *)&address, len);
    if(result == -1) ERROR("oops : client1");

    /*sockfdを介して読み書きができるようにする*/
    len = read(sockfd, &ch, sizeof(ch));
    printf("char from 1 server = %s,read_len=%d,bufsize=%ld\n", ch,len,sizeof(ch));
    memset(ch, 0 , sizeof(ch));

    printf("sleep 1 sec\n");
    sleep(1);

    len = read(sockfd, &ch, sizeof(ch));
    printf("char from 2 server = %s,read_len=%d,bufsize=%ld\n", ch,len,sizeof(ch));
    close(sockfd);
    exit(0);
}
