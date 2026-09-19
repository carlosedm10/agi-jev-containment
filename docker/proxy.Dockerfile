FROM ubuntu/squid:latest

COPY proxy/squid.conf /etc/squid/squid.conf
COPY proxy/auth.sh /proxy/auth.sh
RUN chmod +x /proxy/auth.sh && touch /proxy/tokens
