import ssl
import pytest
from core.egress_policy import EgressTarget
from core.mandatory_proxy import MandatoryProxyConnector,ProxyBoundaryError,ProxyEndpoint

P="93.184.216.34"; O="1.1.1.1"
class Stream:
 def __init__(self,response=b"HTTP/1.1 200 Connection Established\r\n\r\n"): self.response=response; self.sent=[]; self.closed=False
 def settimeout(self,x): pass
 def sendall(self,x): self.sent.append(x)
 def recv(self,n): x,self.response=self.response[:n],self.response[n:]; return x
 def close(self): self.closed=True
class TLS:
 verify_mode=ssl.CERT_REQUIRED; check_hostname=True
 def __init__(self,result=None,fail=False): self.result=result; self.fail=fail; self.names=[]
 def wrap_socket(self,sock,server_hostname):
  self.names.append(server_hostname)
  if self.fail: raise ssl.SSLError("bad certificate")
  return self.result or sock
class Dial:
 def __init__(self,s): self.s=s; self.calls=[]
 def connect(self,t): self.calls.append(t); return type("C",(),{"socket":self.s,"pinned_ip":P})()
def setup(response=b"HTTP/1.1 200 Connection Established\r\n\r\n",fail=False):
 p=ProxyEndpoint(EgressTarget("proxy.example",8443,"https",(P,)))
 o=EgressTarget("origin.example",443,"https",(O,))
 s=Stream(response); d=Dial(s); pt=TLS(s,fail); ot=TLS(s)
 return p,o,s,d,pt,ot

def test_pinned_proxy_numeric_connect_and_tls_sni():
 p,o,s,d,pt,ot=setup()
 c=MandatoryProxyConnector(p,connector=d,proxy_tls_context=pt,origin_tls_context=ot).connect(o)
 assert d.calls==[p.target] and pt.names==["proxy.example"] and ot.names==["origin.example"]
 assert b"CONNECT 1.1.1.1:443" in s.sent[0] and b"origin.example" not in s.sent[0]
 assert c.origin_ip==O

def test_proxy_tls_failure_closes_and_no_fallback():
 p,o,s,d,pt,ot=setup(fail=True)
 with pytest.raises(ProxyBoundaryError): MandatoryProxyConnector(p,connector=d,proxy_tls_context=pt,origin_tls_context=ot).connect(o)
 assert s.closed and len(d.calls)==1

@pytest.mark.parametrize("response",[b"HTTP/1.1 403 Forbidden\r\n\r\n",b"garbage\r\n\r\n",b""])
def test_proxy_failure_is_closed(response):
 p,o,s,d,pt,ot=setup(response)
 with pytest.raises(ProxyBoundaryError): MandatoryProxyConnector(p,connector=d,proxy_tls_context=pt,origin_tls_context=ot).connect(o)
 assert s.closed

def test_tls_verification_cannot_be_disabled():
 p,*_=setup(); ctx=TLS(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
 with pytest.raises(ValueError): MandatoryProxyConnector(p,proxy_tls_context=ctx)
