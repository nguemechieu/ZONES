#ifndef __WEBSOCKET_MQH__
#define __WEBSOCKET_MQH__

#property strict

#define WINHTTP_ACCESS_TYPE_DEFAULT_PROXY            0
#define WINHTTP_NO_PROXY_NAME                        NULL
#define WINHTTP_NO_PROXY_BYPASS                      NULL
#define WINHTTP_NO_REFERER                           NULL
#define WINHTTP_DEFAULT_ACCEPT_TYPES                 NULL
#define WINHTTP_FLAG_SECURE                          0x00800000

#define WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET         114

#define WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE   0
#define WINHTTP_WEB_SOCKET_BINARY_FRAGMENT_BUFFER_TYPE  1
#define WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE     2
#define WINHTTP_WEB_SOCKET_UTF8_FRAGMENT_BUFFER_TYPE    3
#define WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE           4

#define ERROR_SUCCESS                                0
#define WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS       1000

#import "winhttp.dll"
int  WinHttpOpen(string pwszUserAgent, int dwAccessType, string pwszProxyName, string pwszProxyBypass, int dwFlags);
int  WinHttpConnect(int hSession, string pswzServerName, int nServerPort, int dwReserved);
int  WinHttpOpenRequest(int hConnect, string pwszVerb, string pwszObjectName, string pwszVersion, string pwszReferrer, int pwszAcceptTypes, int dwFlags);
bool WinHttpSetOption(int hInternet, int dwOption, uchar &lpBuffer[], int dwBufferLength);
bool WinHttpSendRequest(int hRequest, string pwszHeaders, int dwHeadersLength, int lpOptional, int dwOptionalLength, int dwTotalLength, int dwContext);
bool WinHttpReceiveResponse(int hRequest, int lpReserved);
int  WinHttpWebSocketCompleteUpgrade(int hRequest, int pContext);
int  WinHttpWebSocketSend(int hWebSocket, int eBufferType, uchar &pvBuffer[], int dwBufferLength);
int  WinHttpWebSocketReceive(int hWebSocket, uchar &pvBuffer[], int dwBufferLength, int &pdwBytesRead, int &peBufferType);
int  WinHttpWebSocketClose(int hWebSocket, int usStatus, uchar &pvReason[], int dwReasonLength);
int  WinHttpCloseHandle(int hInternet);
#import

void __ws_string_to_utf8(string text, uchar &out[])
{
   StringToCharArray(text, out, 0, WHOLE_ARRAY, CP_UTF8);
   int n = ArraySize(out);
   if(n > 0 && out[n - 1] == 0)
      ArrayResize(out, n - 1);
}

string __ws_utf8_to_string(const uchar &data[], int len)
{
   if(len <= 0)
      return "";

   uchar temp[];
   ArrayResize(temp, len + 1);
   ArrayCopy(temp, data, 0, 0, len);
   temp[len] = 0;
   return CharArrayToString(temp, 0, len, CP_UTF8);
}

bool __ws_parse_url(string url, bool &secure, string &host, int &port, string &path)
{
   secure = false;
   host = "";
   port = 0;
   path = "/";

   int scheme_pos = StringFind(url, "://");
   if(scheme_pos < 0)
      return false;

   string scheme = StringSubstr(url, 0, scheme_pos);
   string rest   = StringSubstr(url, scheme_pos + 3);

   if(scheme == "ws")
   {
      secure = false;
      port = 80;
   }
   else if(scheme == "wss")
   {
      secure = true;
      port = 443;
   }
   else
      return false;

   int slash_pos = StringFind(rest, "/");
   string hostport;

   if(slash_pos < 0)
   {
      hostport = rest;
      path = "/";
   }
   else
   {
      hostport = StringSubstr(rest, 0, slash_pos);
      path = StringSubstr(rest, slash_pos);
      if(path == "")
         path = "/";
   }

   int colon_pos = StringFind(hostport, ":");
   if(colon_pos >= 0)
   {
      host = StringSubstr(hostport, 0, colon_pos);
      string sPort = StringSubstr(hostport, colon_pos + 1);
      port = StrToInteger(sPort);
      if(port <= 0)
         return false;
   }
   else
      host = hostport;

   return host != "";
}

class CWebSocket
{
private:
   int    m_hSession;
   int    m_hConnect;
   int    m_hRequest;
   int    m_hWebSocket;
   bool   m_connected;
   int    m_lastError;
   string m_userAgent;

   void Reset()
   {
      m_hSession = 0;
      m_hConnect = 0;
      m_hRequest = 0;
      m_hWebSocket = 0;
      m_connected = false;
      m_lastError = 0;
      m_userAgent = "MT4-WebSocket/1.0";
   }

public:
   CWebSocket()
   {
      Reset();
   }

   ~CWebSocket()
   {
      Close();
   }

   int LastError() const { return m_lastError; }
   bool IsConnected() const { return m_connected && m_hWebSocket != 0; }

   bool Connect(string url)
   {
      Close();

      bool secure = false;
      string host = "";
      string path = "/";
      int port = 0;

      if(!__ws_parse_url(url, secure, host, port, path))
      {
         m_lastError = -1;
         return false;
      }

      m_hSession = WinHttpOpen(m_userAgent, WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
      if(m_hSession == 0)
      {
         m_lastError = -2;
         return false;
      }

      m_hConnect = WinHttpConnect(m_hSession, host, port, 0);
      if(m_hConnect == 0)
      {
         m_lastError = -3;
         Close();
         return false;
      }

      int flags = secure ? WINHTTP_FLAG_SECURE : 0;

      m_hRequest = WinHttpOpenRequest(m_hConnect, "GET", path, "HTTP/1.1", WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags);
      if(m_hRequest == 0)
      {
         m_lastError = -4;
         Close();
         return false;
      }

      uchar dummy[];
      ArrayResize(dummy, 0);

      if(!WinHttpSetOption(m_hRequest, WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET, dummy, 0))
      {
         m_lastError = -5;
         Close();
         return false;
      }

      if(!WinHttpSendRequest(m_hRequest, NULL, 0, 0, 0, 0, 0))
      {
         m_lastError = -6;
         Close();
         return false;
      }

      if(!WinHttpReceiveResponse(m_hRequest, 0))
      {
         m_lastError = -7;
         Close();
         return false;
      }

      m_hWebSocket = WinHttpWebSocketCompleteUpgrade(m_hRequest, 0);
      if(m_hWebSocket == 0)
      {
         m_lastError = -8;
         Close();
         return false;
      }

      WinHttpCloseHandle(m_hRequest);
      m_hRequest = 0;
      m_connected = true;
      m_lastError = 0;
      return true;
   }

   bool SendText(string text)
   {
      if(!IsConnected())
      {
         m_lastError = -20;
         return false;
      }

      uchar data[];
      __ws_string_to_utf8(text, data);

      int rc = WinHttpWebSocketSend(
         m_hWebSocket,
         WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE,
         data,
         ArraySize(data)
      );

      m_lastError = rc;
      return rc == ERROR_SUCCESS;
   }

   bool ReceiveText(string &outText, int chunkSize = 4096)
   {
      outText = "";

      if(!IsConnected())
      {
         m_lastError = -30;
         return false;
      }

      uchar chunk[];
      uchar full[];
      ArrayResize(chunk, chunkSize);
      ArrayResize(full, 0);

      while(true)
      {
         int bytesRead = 0;
         int bufferType = -1;

         int rc = WinHttpWebSocketReceive(m_hWebSocket, chunk, chunkSize, bytesRead, bufferType);
         if(rc != ERROR_SUCCESS)
         {
            m_lastError = rc;
            return false;
         }

         if(bufferType == WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE)
         {
            m_connected = false;
            m_lastError = 0;
            return false;
         }

         if(bytesRead > 0)
         {
            int oldSize = ArraySize(full);
            ArrayResize(full, oldSize + bytesRead);
            ArrayCopy(full, chunk, oldSize, 0, bytesRead);
         }

         if(bufferType == WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE)
         {
            outText = __ws_utf8_to_string(full, ArraySize(full));
            m_lastError = 0;
            return true;
         }

         if(bufferType != WINHTTP_WEB_SOCKET_UTF8_FRAGMENT_BUFFER_TYPE)
         {
            m_lastError = -31;
            return false;
         }
      }

      return false;
   }

   bool Close(int status = WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS, string reason = "")
   {
      uchar reasonData[];
      __ws_string_to_utf8(reason, reasonData);

      if(m_hWebSocket != 0)
      {
         WinHttpWebSocketClose(m_hWebSocket, status, reasonData, ArraySize(reasonData));
         WinHttpCloseHandle(m_hWebSocket);
         m_hWebSocket = 0;
      }

      if(m_hRequest != 0)
      {
         WinHttpCloseHandle(m_hRequest);
         m_hRequest = 0;
      }

      if(m_hConnect != 0)
      {
         WinHttpCloseHandle(m_hConnect);
         m_hConnect = 0;
      }

      if(m_hSession != 0)
      {
         WinHttpCloseHandle(m_hSession);
         m_hSession = 0;
      }

      m_connected = false;
      return true;
   }
};

#endif