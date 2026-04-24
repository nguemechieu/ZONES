//+------------------------------------------------------------------+
//|                                                      ProjectName |
//|                                      Copyright 2018, CompanyName |
//|                                       http://www.companyname.net |
//+------------------------------------------------------------------+
#property strict

#include <websocket.mqh>

input string BridgeWebSocketUrl = "ws://127.0.0.1:8090/ws";
input bool PostAllMarketWatchSymbols = false;
input bool DrawZonesOnChart = true;
input int TimerSeconds = 60;
input int MaxSlippage = 5;
input int MagicNumber = 20260316;
input int BarsH1 = 60;
input int BarsM5 = 80;
input int BarsM1 = 120;
input int MaxMarketWatchSymbols = 0;
input int SwingLookback = 3;
input int ScanBars = 180;
input int ZoneProjectionBars = 80;
input int SupportResistanceLookback = 80;
input int MaxSupplyZones = 3;
input int MaxDemandZones = 3;
input int MaxLiquidityZones = 2;
input double ZonePaddingPoints = 60.0;
input double LiquidityTolerancePoints = 45.0;
input int ZigZagDepth = 12;
input int ZigZagDeviation = 5;
input int ZigZagBackstep = 3;
input double TempZoneMinThicknessPoints = 45.0;
input double TempZoneMaxThicknessPoints = 180.0;
input double MainZoneMinThicknessPoints = 60.0;
input double MainZoneMaxThicknessPoints = 260.0;
input double ZoneMergeTolerancePoints = 35.0;
input int MinimumM5Touches = 3;
input bool DrawStructureLabels = true;
input bool EnableBridgePosting = true;
input int BridgeRetryCount = 2;
input int BridgeRetryDelayMs = 150;
input string ExecutionStyle = "advanced";
input string AdvancedConfirmationTimeframe = "M5";
input int AdvancedRetestLimit = 2;
input string RetestEntryMode = "close";
input bool EnableAutoExecution = false;
input double AutoExecutionLots = 0.10;
input bool RequireAiAgreementForAutoExecution = false;
input color SupplyColor = clrTomato;
input color DemandColor = clrDeepSkyBlue;
input color LiquidityColor = clrGold;
input color ResistanceColor = clrOrangeRed;
input color SupportColor = clrDodgerBlue;

input double MaxSpreadPoints = 35.0;
input double MaxRiskPerTradePct = 1.00;
input double MaxTotalExposurePct = 30.0;
input int MaxOpenTradesPerSymbol = 2;
input int MaxCommandsPerPoll = 10;
input int TradeCooldownSeconds = 10;
input bool RejectIfStopsTooClose = true;
input bool RejectIfTradingDisabled = true;
input bool RejectDuplicateCommandIds = true;
input bool IncludeOnlyMagicPositionsInPayload = false;

const string ZonePrefix = "ZONES_";

CWebSocket g_ws;
datetime g_lastTradeTime = 0;
string g_lastCommandIds[128];
int g_lastCommandIndex = 0;
datetime g_lastBridgeSuccess = 0;
string g_lastBridgeError = "";
int g_bridgeFailureCount = 0;

struct ZoneRecord
  {
   string            id;
   string            timeframe;
   string            anchorTimeframe;
   string            kind;
   string            family;
   string            status;
   string            strengthLabel;
   string            modeBias;
   string            priceRelation;
   string            structureLabel;
   int               strength;
   int               zigzagCount;
   int               fractalCount;
   int               touchCount;
   int               retestCount;
   int               originShift;
   datetime          originTime;
   double            originPrice;
   double            bodyStart;
   double            lower;
   double            upper;
  };

struct SwingRecord
  {
   int               shift;
   datetime          swingTime;
   double            price;
   bool              isHigh;
   bool              fromZigZag;
   bool              fromFractal;
   string            label;
  };

struct StructureEventRecord
  {
   string            eventName;
   string            direction;
   string            structureLabel;
   int               originShift;
   datetime          eventTime;
   double            level;
  };

struct ExecutionPlanRecord
  {
   bool              allowed;
   string            prediction;
   string            style;
   string            confirmationTimeframe;
   string            rrrState;
   string            bosDirection;
   string            reason;
   string            activeZoneId;
   string            activeZoneKind;
   string            zoneState;
   int               retestCount;
   double            score;
   double            entryPrice;
   double            stopLoss;
   double            takeProfit;
  };

struct AiBridgeRecord
  {
   bool              available;
   string            prediction;
   double            confidence;
   string            reason;
   string            zoneState;
   string            executionHint;
   string            riskHint;
   string            modelStatus;
   datetime          receivedAt;
   string            raw;
  };

ZoneRecord g_chartZones[];
SwingRecord g_chartSwings[];
StructureEventRecord g_chartEvents[];
ExecutionPlanRecord g_executionPlan;
AiBridgeRecord g_aiBridge;
string g_structureBias = "neutral";
string g_structureLabelsCsv = "";

// ============================================================
// HELPERS
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string StringRepeat(string value, int count)
  {
   if(count <= 0 || value == "")
      return "";

   string result = "";
   for(int i = 0; i < count; i++)
      result += value;

   return result;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string TerminalAccountId()
  {
   return IntegerToString(AccountNumber());
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string EscapeJson(string value)
  {
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   return value;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string CommandValue(string commandText, string key)
  {
   string parts[];
   int total = StringSplit(commandText, '|', parts);
   string prefix = key + "=";

   for(int index = 0; index < total; index++)
     {
      if(StringFind(parts[index], prefix, 0) == 0)
         return StringSubstr(parts[index], StringLen(prefix));
     }

   return "";
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string JsonValue(string json, string key)
  {
   string token = "\"" + key + "\":";
   int p = StringFind(json, token, 0);
   if(p < 0)
      return "";

   p += StringLen(token);

   while(p < StringLen(json) && (StringGetChar(json, p) == ' ' || StringGetChar(json, p) == 9))
      p++;

   if(p >= StringLen(json))
      return "";

   if(StringGetChar(json, p) == '"')
     {
      p++;
      int end = p;
      while(end < StringLen(json))
        {
         if(StringGetChar(json, end) == '"' && StringGetChar(json, end - 1) != '\\')
            break;
         end++;
        }
      if(end <= StringLen(json))
         return StringSubstr(json, p, end - p);
      return "";
     }

   int end2 = p;
   while(end2 < StringLen(json))
     {
      int ch = StringGetChar(json, end2);
      if(ch == ',' || ch == '}' || ch == '\r' || ch == '\n')
         break;
      end2++;
     }

   return StringTrim(StringSubstr(json, p, end2 - p));
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string StringTrim(string text)
  {
   StringTrimLeft(text);
   StringTrimRight(text);
   return text;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool EnsureWebSocket()
  {
   if(g_ws.IsConnected())
      return true;

   if(!EnableBridgePosting)
      return false;

   if(!g_ws.Connect(BridgeWebSocketUrl))
     {
      g_lastBridgeError = "connect:" + IntegerToString(g_ws.LastError());
      g_bridgeFailureCount++;
      Print("ZONES bridge connect failed: ", g_ws.LastError(), " url=", BridgeWebSocketUrl);
      return false;
     }

   g_lastBridgeError = "";
   Print("ZONES bridge connected: ", BridgeWebSocketUrl);
   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool WsRequest(string requestJson, string &replyJson)
  {
   replyJson = "";
   if(!EnableBridgePosting)
      return false;

   for(int attempt = 0; attempt <= BridgeRetryCount; attempt++)
     {
      if(!EnsureWebSocket())
        {
         if(attempt < BridgeRetryCount)
            Sleep(BridgeRetryDelayMs);
         continue;
        }

      if(!g_ws.SendText(requestJson))
        {
         g_lastBridgeError = "send:" + IntegerToString(g_ws.LastError());
         Print("ZONES bridge send failed: ", g_ws.LastError(), " attempt=", attempt + 1);
         g_ws.Close();
         if(attempt < BridgeRetryCount)
            Sleep(BridgeRetryDelayMs);
         continue;
        }

      if(!g_ws.ReceiveText(replyJson))
        {
         g_lastBridgeError = "receive:" + IntegerToString(g_ws.LastError());
         Print("ZONES bridge receive failed: ", g_ws.LastError(), " attempt=", attempt + 1);
         g_ws.Close();
         if(attempt < BridgeRetryCount)
            Sleep(BridgeRetryDelayMs);
         continue;
        }

      g_lastBridgeSuccess = TimeCurrent();
      g_lastBridgeError = "";
      return true;
     }

   g_bridgeFailureCount++;
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SendCommandAck(string commandId, string status, string message)
  {
   string req =
      "{"
      "\"action\":\"command_ack\","
      "\"account_id\":\"" + EscapeJson(TerminalAccountId()) + "\","
      "\"id\":\"" + EscapeJson(commandId) + "\","
      "\"status\":\"" + EscapeJson(status) + "\","
      "\"message\":\"" + EscapeJson(message) + "\""
      "}";

   string reply = "";
   if(!WsRequest(req, reply))
      return false;

   return JsonValue(reply, "status") == "ok";
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SelectTicket(int ticket)
  {
   return OrderSelect(ticket, SELECT_BY_TICKET);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OrderTypeFromCommand(string commandType)
  {
   if(commandType == "buy_limit")
      return OP_BUYLIMIT;
   if(commandType == "sell_limit")
      return OP_SELLLIMIT;
   if(commandType == "buy_stop")
      return OP_BUYSTOP;
   if(commandType == "sell_stop")
      return OP_SELLSTOP;
   return -1;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsPendingOrderType(int orderType)
  {
   return orderType == OP_BUYLIMIT || orderType == OP_SELLLIMIT || orderType == OP_BUYSTOP || orderType == OP_SELLSTOP;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsMarketOrderType(int orderType)
  {
   return orderType == OP_BUY || orderType == OP_SELL;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string ErrorDescriptionEx(int code)
  {
   switch(code)
     {
      case 0:
         return "No error";
      case 1:
         return "No error returned";
      case 2:
         return "Common error";
      case 3:
         return "Invalid trade parameters";
      case 4:
         return "Trade server busy";
      case 5:
         return "Old terminal version";
      case 6:
         return "No connection";
      case 8:
         return "Too frequent requests";
      case 64:
         return "Account disabled";
      case 65:
         return "Invalid account";
      case 128:
         return "Trade timeout";
      case 129:
         return "Invalid price";
      case 130:
         return "Invalid stops";
      case 131:
         return "Invalid trade volume";
      case 132:
         return "Market closed";
      case 133:
         return "Trade disabled";
      case 134:
         return "Not enough money";
      case 135:
         return "Price changed";
      case 136:
         return "Off quotes";
      case 137:
         return "Broker busy";
      case 138:
         return "Requote";
      case 139:
         return "Order locked";
      case 140:
         return "Long positions only allowed";
      case 141:
         return "Too many requests";
      case 145:
         return "Modification denied";
      case 146:
         return "Trade context busy";
      case 147:
         return "Expirations denied";
      case 148:
         return "Too many orders";
      case 149:
         return "Hedge prohibited";
      case 150:
         return "FIFO rule";
      default:
         return "Unknown trade error";
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SendTradeErrorAck(string commandId, string stage, string extra)
  {
   int code = GetLastError();
   string message = stage + " failed | code=" + IntegerToString(code) + " | " + ErrorDescriptionEx(code);
   if(extra != "")
      message += " | " + extra;
   ResetLastError();
   return SendCommandAck(commandId, "error", message);
  }

// ============================================================
// EXECUTION SAFETY
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SeenCommandId(string commandId)
  {
   if(commandId == "")
      return false;

   for(int i = 0; i < ArraySize(g_lastCommandIds); i++)
     {
      if(g_lastCommandIds[i] == commandId)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void RememberCommandId(string commandId)
  {
   if(commandId == "")
      return;

   g_lastCommandIds[g_lastCommandIndex] = commandId;
   g_lastCommandIndex++;

   if(g_lastCommandIndex >= ArraySize(g_lastCommandIds))
      g_lastCommandIndex = 0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double NormalizeLotsForSymbol(string symbolName, double lots)
  {
   double minLot = MarketInfo(symbolName, MODE_MINLOT);
   double maxLot = MarketInfo(symbolName, MODE_MAXLOT);
   double lotStep = MarketInfo(symbolName, MODE_LOTSTEP);

   if(lotStep <= 0.0)
      lotStep = 0.01;

   lots = MathMax(minLot, MathMin(maxLot, lots));
   lots = MathFloor(lots / lotStep) * lotStep;

   if(lots < minLot)
      lots = minLot;

   return NormalizeDouble(lots, 2);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double NormalizePriceForSymbol(string symbolName, double price)
  {
   int digits = (int)MarketInfo(symbolName, MODE_DIGITS);
   return NormalizeDouble(price, digits);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double SymbolPointValue(string symbolName)
  {
   double point = MarketInfo(symbolName, MODE_POINT);
   if(point <= 0.0)
      point = Point;
   return point;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int SymbolDigitsValue(string symbolName)
  {
   int digits = (int)MarketInfo(symbolName, MODE_DIGITS);
   if(digits < 0)
      digits = Digits;
   return digits;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double CurrentSpreadPoints(string symbolName)
  {
   return MarketInfo(symbolName, MODE_SPREAD);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool TradingAllowedForSymbol(string symbolName)
  {
   if(!IsConnected())
      return false;

   if(IsTradeContextBusy())
      return false;

   if(!IsTradeAllowed())
      return false;

   if(MarketInfo(symbolName, MODE_TRADEALLOWED) == 0)
      return false;

   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SymbolHasFreshQuotes(string symbolName)
  {
   double bid = MarketInfo(symbolName, MODE_BID);
   double ask = MarketInfo(symbolName, MODE_ASK);
   return (bid > 0.0 && ask > 0.0 && ask >= bid);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int CountOpenTradesForSymbol(string symbolName)
  {
   int total = 0;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != symbolName)
         continue;
      if(OrderMagicNumber() != MagicNumber)
         continue;
      if(OrderType() <= OP_SELL)
         total++;
     }

   return total;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double CurrentExposurePct()
  {
   if(AccountEquity() <= 0.0)
      return 0.0;
   return (AccountMargin() / AccountEquity()) * 100.0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool InTradeCooldown()
  {
   if(g_lastTradeTime <= 0)
      return false;
   return (TimeCurrent() - g_lastTradeTime) < TradeCooldownSeconds;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool HasEnoughMargin(string symbolName, int orderType, double lots)
  {
   double marginRequired = MarketInfo(symbolName, MODE_MARGINREQUIRED) * lots;

   if(marginRequired <= 0.0)
      return AccountFreeMarginCheck(symbolName, orderType, lots) > 0.0;

   return AccountFreeMargin() > marginRequired;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool PendingPriceValid(string symbolName, int orderType, double price, string &reason)
  {
   double bid = MarketInfo(symbolName, MODE_BID);
   double ask = MarketInfo(symbolName, MODE_ASK);

   if(orderType == OP_BUYLIMIT && price >= ask)
     {
      reason = "Buy limit must be below ask";
      return false;
     }

   if(orderType == OP_SELLLIMIT && price <= bid)
     {
      reason = "Sell limit must be above bid";
      return false;
     }

   if(orderType == OP_BUYSTOP && price <= ask)
     {
      reason = "Buy stop must be above ask";
      return false;
     }

   if(orderType == OP_SELLSTOP && price >= bid)
     {
      reason = "Sell stop must be below bid";
      return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool StopsValid(string symbolName, int orderType, double price, double sl, double tp, string &reason)
  {
   double point = SymbolPointValue(symbolName);
   int stopLevel = (int)MarketInfo(symbolName, MODE_STOPLEVEL);
   double minDistance = stopLevel * point;

   if(!RejectIfStopsTooClose)
      return true;

   if(sl > 0.0)
     {
      if(orderType == OP_BUY || orderType == OP_BUYLIMIT || orderType == OP_BUYSTOP)
        {
         if((price - sl) < minDistance)
           {
            reason = "SL too close";
            return false;
           }
        }
      else
        {
         if((sl - price) < minDistance)
           {
            reason = "SL too close";
            return false;
           }
        }
     }

   if(tp > 0.0)
     {
      if(orderType == OP_BUY || orderType == OP_BUYLIMIT || orderType == OP_BUYSTOP)
        {
         if((tp - price) < minDistance)
           {
            reason = "TP too close";
            return false;
           }
        }
      else
        {
         if((price - tp) < minDistance)
           {
            reason = "TP too close";
            return false;
           }
        }
     }

   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool RiskWithinLimit(string symbolName, int orderType, double lots, double price, double sl)
  {
   if(sl <= 0.0 || AccountEquity() <= 0.0)
      return true;

   double tickValue = MarketInfo(symbolName, MODE_TICKVALUE);
   double tickSize  = MarketInfo(symbolName, MODE_TICKSIZE);
   double point     = SymbolPointValue(symbolName);

   if(tickValue <= 0.0 || tickSize <= 0.0 || point <= 0.0)
      return true;

   double distance = MathAbs(price - sl);
   double pointsDistance = distance / point;
   double valuePerPointPerLot = tickValue * (point / tickSize);
   double riskMoney = pointsDistance * valuePerPointPerLot * lots;
   double riskPct = (riskMoney / AccountEquity()) * 100.0;

   return riskPct <= MaxRiskPerTradePct;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool PreTradeCheck(
   string commandId,
   string symbolName,
   int orderType,
   double &lots,
   double &price,
   double &sl,
   double &tp,
   string &reason
)
  {
   if(RejectDuplicateCommandIds && SeenCommandId(commandId))
     {
      reason = "Duplicate command id";
      return false;
     }

   if(symbolName == "")
     {
      reason = "Empty symbol";
      return false;
     }

   if(RejectIfTradingDisabled && !TradingAllowedForSymbol(symbolName))
     {
      reason = "Trading not allowed";
      return false;
     }

   if(!SymbolHasFreshQuotes(symbolName))
     {
      reason = "No fresh quotes";
      return false;
     }

   if(CurrentSpreadPoints(symbolName) > MaxSpreadPoints)
     {
      reason = "Spread too high";
      return false;
     }

   if(InTradeCooldown() && IsMarketOrderType(orderType))
     {
      reason = "Trade cooldown active";
      return false;
     }

   if(CountOpenTradesForSymbol(symbolName) >= MaxOpenTradesPerSymbol && IsMarketOrderType(orderType))
     {
      reason = "Max open trades per symbol reached";
      return false;
     }

   if(CurrentExposurePct() >= MaxTotalExposurePct)
     {
      reason = "Total exposure limit reached";
      return false;
     }

   lots = NormalizeLotsForSymbol(symbolName, lots);
   if(lots <= 0.0)
     {
      reason = "Invalid lot size";
      return false;
     }

   price = NormalizePriceForSymbol(symbolName, price);
   if(sl > 0.0)
      sl = NormalizePriceForSymbol(symbolName, sl);
   if(tp > 0.0)
      tp = NormalizePriceForSymbol(symbolName, tp);

   if(IsPendingOrderType(orderType))
     {
      if(price <= 0.0)
        {
         reason = "Pending order price is required";
         return false;
        }

      if(!PendingPriceValid(symbolName, orderType, price, reason))
         return false;
     }

   if(!HasEnoughMargin(symbolName, IsPendingOrderType(orderType) ? OP_BUY : orderType, lots))
     {
      reason = "Insufficient margin";
      return false;
     }

   if(!StopsValid(symbolName, orderType, price, sl, tp, reason))
      return false;

   if(!RiskWithinLimit(symbolName, orderType, lots, price, sl))
     {
      reason = "Risk per trade exceeds configured limit";
      return false;
     }

   return true;
  }

// ============================================================
// COMMAND EXECUTION
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool ExecuteCommand(string commandText)
  {
   string commandId = CommandValue(commandText, "id");
   string commandType = CommandValue(commandText, "type");
   string symbolName = CommandValue(commandText, "symbol");

   if(symbolName == "")
      symbolName = Symbol();

   RefreshRates();

   if(commandType == "")
     {
      SendCommandAck(commandId, "error", "Missing command type");
      return false;
     }

   if(commandType == "alert")
     {
      string message = CommandValue(commandText, "message");
      Alert("ZONES: ", message);
      SendCommandAck(commandId, "ok", "Alert executed");
      RememberCommandId(commandId);
      return true;
     }

   if(commandType == "market_buy" || commandType == "market_sell")
     {
      double lots = StrToDouble(CommandValue(commandText, "lot"));
      double sl = StrToDouble(CommandValue(commandText, "sl"));
      double tp = StrToDouble(CommandValue(commandText, "tp"));
      string comment = CommandValue(commandText, "comment");

      int orderType = (commandType == "market_buy") ? OP_BUY : OP_SELL;
      double price = (commandType == "market_buy")
                     ? MarketInfo(symbolName, MODE_ASK)
                     : MarketInfo(symbolName, MODE_BID);

      string rejectReason = "";
      if(!PreTradeCheck(commandId, symbolName, orderType, lots, price, sl, tp, rejectReason))
        {
         SendCommandAck(commandId, "rejected", rejectReason);
         return false;
        }

      RefreshRates();
      price = (commandType == "market_buy")
              ? NormalizePriceForSymbol(symbolName, MarketInfo(symbolName, MODE_ASK))
              : NormalizePriceForSymbol(symbolName, MarketInfo(symbolName, MODE_BID));

      int ticket = OrderSend(symbolName, orderType, lots, price, MaxSlippage, sl, tp, comment, MagicNumber, 0, clrNONE);

      if(ticket < 0)
         return SendTradeErrorAck(commandId, "Market OrderSend", "symbol=" + symbolName);

      g_lastTradeTime = TimeCurrent();
      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "ticket=" + IntegerToString(ticket) + "|symbol=" + symbolName);
      return true;
     }

   if(commandType == "buy_limit" || commandType == "sell_limit" || commandType == "buy_stop" || commandType == "sell_stop")
     {
      double lots = StrToDouble(CommandValue(commandText, "lot"));
      double price = StrToDouble(CommandValue(commandText, "price"));
      double sl = StrToDouble(CommandValue(commandText, "sl"));
      double tp = StrToDouble(CommandValue(commandText, "tp"));
      string comment = CommandValue(commandText, "comment");
      int orderType = OrderTypeFromCommand(commandType);

      string rejectReason = "";
      if(!PreTradeCheck(commandId, symbolName, orderType, lots, price, sl, tp, rejectReason))
        {
         SendCommandAck(commandId, "rejected", rejectReason);
         return false;
        }

      int ticket = OrderSend(symbolName, orderType, lots, price, MaxSlippage, sl, tp, comment, MagicNumber, 0, clrNONE);

      if(ticket < 0)
         return SendTradeErrorAck(commandId, "Pending OrderSend", "symbol=" + symbolName);

      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "ticket=" + IntegerToString(ticket) + "|symbol=" + symbolName);
      return true;
     }

   if(commandType == "close_ticket")
     {
      int ticket = StrToInteger(CommandValue(commandText, "ticket"));

      if(!SelectTicket(ticket))
        {
         SendCommandAck(commandId, "error", "Ticket not found");
         return false;
        }

      int orderType = OrderType();
      if(orderType > OP_SELL)
        {
         SendCommandAck(commandId, "error", "Ticket is not an open market position");
         return false;
        }

      double closePrice = (orderType == OP_BUY)
                          ? NormalizePriceForSymbol(OrderSymbol(), MarketInfo(OrderSymbol(), MODE_BID))
                          : NormalizePriceForSymbol(OrderSymbol(), MarketInfo(OrderSymbol(), MODE_ASK));

      if(!OrderClose(ticket, OrderLots(), closePrice, MaxSlippage, clrNONE))
         return SendTradeErrorAck(commandId, "OrderClose", "ticket=" + IntegerToString(ticket));

      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "Closed ticket=" + IntegerToString(ticket));
      return true;
     }

   if(commandType == "delete_ticket")
     {
      int ticket = StrToInteger(CommandValue(commandText, "ticket"));

      if(!SelectTicket(ticket))
        {
         SendCommandAck(commandId, "error", "Ticket not found");
         return false;
        }

      if(OrderType() <= OP_SELL)
        {
         SendCommandAck(commandId, "error", "Ticket is not a pending order");
         return false;
        }

      if(!OrderDelete(ticket, clrNONE))
         return SendTradeErrorAck(commandId, "OrderDelete", "ticket=" + IntegerToString(ticket));

      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "Deleted pending ticket=" + IntegerToString(ticket));
      return true;
     }

   if(commandType == "modify_ticket")
     {
      int ticket = StrToInteger(CommandValue(commandText, "ticket"));
      double price = StrToDouble(CommandValue(commandText, "price"));
      double sl = StrToDouble(CommandValue(commandText, "sl"));
      double tp = StrToDouble(CommandValue(commandText, "tp"));

      if(!SelectTicket(ticket))
        {
         SendCommandAck(commandId, "error", "Ticket not found");
         return false;
        }

      string orderSymbol = OrderSymbol();
      int orderType = OrderType();

      if(price <= 0.0)
         price = OrderOpenPrice();

      price = NormalizePriceForSymbol(orderSymbol, price);
      if(sl > 0.0)
         sl = NormalizePriceForSymbol(orderSymbol, sl);
      if(tp > 0.0)
         tp = NormalizePriceForSymbol(orderSymbol, tp);

      string rejectReason = "";
      if(!StopsValid(orderSymbol, orderType, price, sl, tp, rejectReason))
        {
         SendCommandAck(commandId, "rejected", rejectReason);
         return false;
        }

      if(!OrderModify(ticket, price, sl, tp, OrderExpiration(), clrNONE))
         return SendTradeErrorAck(commandId, "OrderModify", "ticket=" + IntegerToString(ticket));

      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "Modified ticket=" + IntegerToString(ticket));
      return true;
     }

   if(commandType == "close_all")
     {
      string filterSymbol = CommandValue(commandText, "filter_symbol");
      int closed = 0;

      for(int index = OrdersTotal() - 1; index >= 0; index--)
        {
         if(!OrderSelect(index, SELECT_BY_POS, MODE_TRADES))
            continue;

         if(filterSymbol != "" && OrderSymbol() != filterSymbol)
            continue;

         if(OrderType() > OP_SELL)
            continue;

         double closePrice = (OrderType() == OP_BUY)
                             ? NormalizePriceForSymbol(OrderSymbol(), MarketInfo(OrderSymbol(), MODE_BID))
                             : NormalizePriceForSymbol(OrderSymbol(), MarketInfo(OrderSymbol(), MODE_ASK));

         if(OrderClose(OrderTicket(), OrderLots(), closePrice, MaxSlippage, clrNONE))
            closed++;
        }

      RememberCommandId(commandId);
      SendCommandAck(commandId, "ok", "closed=" + IntegerToString(closed));
      return true;
     }

   SendCommandAck(commandId, "error", "Unsupported command type: " + commandType);
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void PollCommandQueueForSymbol(string symbolName)
  {
   int processed = 0;

   while(processed < MaxCommandsPerPoll)
     {
      string request =
         "{"
         "\"action\":\"fetch_command\","
         "\"account_id\":\"" + EscapeJson(TerminalAccountId()) + "\","
         "\"symbol\":\"" + EscapeJson(symbolName) + "\""
         "}";

      string reply = "";
      if(!WsRequest(request, reply))
         return;

      string status = JsonValue(reply, "status");
      if(status != "ok")
         return;

      string response = JsonValue(reply, "command");
      if(response == "")
         return;

      ExecuteCommand(response);
      processed++;
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void PollCommands()
  {
   if(!PostAllMarketWatchSymbols)
     {
      PollCommandQueueForSymbol(Symbol());
      return;
     }

   int totalSymbols = SymbolsTotal(true);
   int processed = 0;

   for(int index = 0; index < totalSymbols; index++)
     {
      string symbolName = SymbolName(index, true);
      if(symbolName == "")
         continue;

      PollCommandQueueForSymbol(symbolName);
      processed++;

      if(MaxMarketWatchSymbols > 0 && processed >= MaxMarketWatchSymbols)
         break;
     }
  }

// ============================================================
// ZONE DRAWING / VISUALS
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double SymbolPointSize(string symbolName)
  {
   double value = MarketInfo(symbolName, MODE_POINT);
   if(value <= 0.0)
      value = Point;
   return value;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double ClampDouble(double value, double minValue, double maxValue)
  {
   if(value < minValue)
      return minValue;
   if(value > maxValue)
      return maxValue;
   return value;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string BoolText(bool value)
  {
   return value ? "true" : "false";
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string TimeframeLabelByEnum(int timeframe)
  {
   switch(timeframe)
     {
      case PERIOD_M1:
         return "1M";
      case PERIOD_M5:
         return "5M";
      case PERIOD_M15:
         return "15M";
      case PERIOD_M30:
         return "30M";
      case PERIOD_H1:
         return "1H";
      case PERIOD_H4:
         return "4H";
      case PERIOD_D1:
         return "1D";
      default:
         return "5M";
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int TimeframeFromInput(string value)
  {
   string normalized = value;
   StringTrimLeft(normalized);
   StringTrimRight(normalized);

   if(normalized == "M1" || normalized == "1M")
      return PERIOD_M1;
   if(normalized == "M5" || normalized == "5M")
      return PERIOD_M5;
   if(normalized == "M15" || normalized == "15M")
      return PERIOD_M15;
   if(normalized == "M30" || normalized == "30M")
      return PERIOD_M30;
   if(normalized == "H1" || normalized == "1H")
      return PERIOD_H1;
   if(normalized == "H4" || normalized == "4H")
      return PERIOD_H4;
   if(normalized == "D1" || normalized == "1D")
      return PERIOD_D1;
   return PERIOD_M5;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int TimeframeSeconds(int timeframe)
  {
   switch(timeframe)
     {
      case PERIOD_M1:
         return 60;
      case PERIOD_M5:
         return 300;
      case PERIOD_M15:
         return 900;
      case PERIOD_M30:
         return 1800;
      case PERIOD_H1:
         return 3600;
      case PERIOD_H4:
         return 14400;
      case PERIOD_D1:
         return 86400;
      default:
         return 60;
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double PriceDistancePoints(string symbolName, double firstPrice, double secondPrice)
  {
   double pointValue = SymbolPointSize(symbolName);
   if(pointValue <= 0.0)
      return 0.0;
   return MathAbs(firstPrice - secondPrice) / pointValue;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string CurrentTimeframeLabel()
  {
   return TimeframeLabelByEnum(Period());
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double ZoneThicknessMinPrice(string symbolName, string family)
  {
   double pointValue = SymbolPointSize(symbolName);
   if(family == "main")
      return MainZoneMinThicknessPoints * pointValue;
   return TempZoneMinThicknessPoints * pointValue;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double ZoneThicknessMaxPrice(string symbolName, string family)
  {
   double pointValue = SymbolPointSize(symbolName);
   if(family == "main")
      return MainZoneMaxThicknessPoints * pointValue;
   return TempZoneMaxThicknessPoints * pointValue;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ResetExecutionPlan(ExecutionPlanRecord &plan)
  {
   plan.allowed = false;
   plan.prediction = "HOLD";
   plan.style = ExecutionStyle;
   plan.confirmationTimeframe = AdvancedConfirmationTimeframe;
   plan.rrrState = "none";
   plan.bosDirection = "none";
   plan.reason = "No eligible zone setup.";
   plan.activeZoneId = "";
   plan.activeZoneKind = "";
   plan.zoneState = "";
   plan.retestCount = 0;
   plan.score = 0.0;
   plan.entryPrice = 0.0;
   plan.stopLoss = 0.0;
   plan.takeProfit = 0.0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CandleTouchesZone(string symbolName, int timeframe, int shift, ZoneRecord &zone)
  {
   double candleHigh = iHigh(symbolName, timeframe, shift);
   double candleLow = iLow(symbolName, timeframe, shift);
   return candleLow <= zone.upper && candleHigh >= zone.lower;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CandleShowsRespect(string symbolName, int timeframe, int shift, ZoneRecord &zone)
  {
   if(!CandleTouchesZone(symbolName, timeframe, shift, zone))
      return false;

   double candleOpen = iOpen(symbolName, timeframe, shift);
   double candleClose = iClose(symbolName, timeframe, shift);

   if(zone.kind == "demand")
      return candleClose >= zone.upper && candleClose >= candleOpen;

   return candleClose <= zone.lower && candleClose <= candleOpen;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CandleShowsReject(string symbolName, int timeframe, int shift, ZoneRecord &zone)
  {
   if(!CandleTouchesZone(symbolName, timeframe, shift, zone))
      return false;

   double candleOpen = iOpen(symbolName, timeframe, shift);
   double candleClose = iClose(symbolName, timeframe, shift);
   double probe = ZonePaddingPoints * SymbolPointSize(symbolName) * 0.12;

   if(zone.kind == "demand")
      return iLow(symbolName, timeframe, shift) <= zone.lower + probe && candleClose > candleOpen && candleClose >= zone.upper;

   return iHigh(symbolName, timeframe, shift) >= zone.upper - probe && candleClose < candleOpen && candleClose <= zone.lower;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int CountRecentRetests(string symbolName, int timeframe, ZoneRecord &zone, int maxBars)
  {
   int sequences = 0;
   bool previousTouch = false;
   int barsAvailable = iBars(symbolName, timeframe);

   for(int shift = MathMin(maxBars, barsAvailable - 1); shift >= 1; shift--)
     {
      bool currentTouch = CandleTouchesZone(symbolName, timeframe, shift, zone);
      if(currentTouch && !previousTouch)
         sequences++;
      previousTouch = currentTouch;
     }

   return sequences;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool DetectLowerTimeframeBos(string symbolName, int timeframe, bool bullish, double &levelOut)
  {
   levelOut = 0.0;
   if(iBars(symbolName, timeframe) < 20)
      return false;

   if(bullish)
     {
      int highestShift = iHighest(symbolName, timeframe, MODE_HIGH, 12, 2);
      levelOut = iHigh(symbolName, timeframe, highestShift);
      return iClose(symbolName, timeframe, 1) > levelOut;
     }

   int lowestShift = iLowest(symbolName, timeframe, MODE_LOW, 12, 2);
   levelOut = iLow(symbolName, timeframe, lowestShift);
   return iClose(symbolName, timeframe, 1) < levelOut;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsHighSwing(string symbolName, int timeframe, int shift, double pivotPrice)
  {
   return MathAbs(pivotPrice - iHigh(symbolName, timeframe, shift)) <= MathAbs(pivotPrice - iLow(symbolName, timeframe, shift));
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AddSwingRecord(SwingRecord &swings[], int shift, datetime swingTime, double price, bool isHigh, bool fromZigZag, bool fromFractal)
  {
   int count = ArraySize(swings);
   ArrayResize(swings, count + 1);
   swings[count].shift = shift;
   swings[count].swingTime = swingTime;
   swings[count].price = price;
   swings[count].isHigh = isHigh;
   swings[count].fromZigZag = fromZigZag;
   swings[count].fromFractal = fromFractal;
   swings[count].label = "";
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AddStructureEvent(StructureEventRecord &events[], string eventName, string direction, string structureLabel, int originShift, datetime eventTime, double level)
  {
   int count = ArraySize(events);
   ArrayResize(events, count + 1);
   events[count].eventName = eventName;
   events[count].direction = direction;
   events[count].structureLabel = structureLabel;
   events[count].originShift = originShift;
   events[count].eventTime = eventTime;
   events[count].level = level;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AppendLabelCsv(string &csv, string value)
  {
   if(value == "")
      return;
   if(csv != "")
      csv += ",";
   csv += value;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CollectH1Structure(string symbolName, SwingRecord &swings[], StructureEventRecord &events[], string &structureBias, string &labelsCsv)
  {
   ArrayResize(swings, 0);
   ArrayResize(events, 0);
   structureBias = "neutral";
   labelsCsv = "";

   for(int shift = MathMin(ScanBars, iBars(symbolName, PERIOD_H1) - 1); shift >= 2; shift--)
     {
      double pivot = iCustom(symbolName, PERIOD_H1, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, shift);
      if(pivot == 0.0)
         continue;

      AddSwingRecord(swings, shift, iTime(symbolName, PERIOD_H1, shift), pivot, IsHighSwing(symbolName, PERIOD_H1, shift, pivot), true, false);
     }

   double previousHigh = 0.0;
   double previousLow = 0.0;
   bool hasPreviousHigh = false;
   bool hasPreviousLow = false;
   string latestHighLabel = "";
   string latestLowLabel = "";

   for(int index = 0; index < ArraySize(swings); index++)
     {
      if(swings[index].isHigh)
        {
         if(!hasPreviousHigh)
            swings[index].label = "HH";
         else
            if(PriceDistancePoints(symbolName, swings[index].price, previousHigh) <= ZoneMergeTolerancePoints)
               swings[index].label = "EQHH";
            else
               if(swings[index].price > previousHigh)
                  swings[index].label = "HH";
               else
                  swings[index].label = "LH";

         previousHigh = swings[index].price;
         hasPreviousHigh = true;
         latestHighLabel = swings[index].label;
        }
      else
        {
         if(!hasPreviousLow)
            swings[index].label = "LL";
         else
            if(PriceDistancePoints(symbolName, swings[index].price, previousLow) <= ZoneMergeTolerancePoints)
               swings[index].label = "EQLL";
            else
               if(swings[index].price > previousLow)
                  swings[index].label = "HL";
               else
                  swings[index].label = "LL";

         previousLow = swings[index].price;
         hasPreviousLow = true;
         latestLowLabel = swings[index].label;
        }

      AppendLabelCsv(labelsCsv, swings[index].label);
     }

   if((latestHighLabel == "HH" || latestHighLabel == "EQHH") && (latestLowLabel == "HL" || latestLowLabel == "EQLL"))
      structureBias = "bullish";
   else
      if(latestHighLabel == "LH" && latestLowLabel == "LL")
         structureBias = "bearish";

   double closeH1 = iClose(symbolName, PERIOD_H1, 1);
   double lastHighLevel = 0.0;
   double lastLowLevel = 0.0;

   for(int reverse = ArraySize(swings) - 1; reverse >= 0; reverse--)
     {
      if(swings[reverse].isHigh && lastHighLevel == 0.0)
         lastHighLevel = swings[reverse].price;
      if(!swings[reverse].isHigh && lastLowLevel == 0.0)
         lastLowLevel = swings[reverse].price;
      if(lastHighLevel > 0.0 && lastLowLevel > 0.0)
         break;
     }

   double bosPadding = SymbolPointSize(symbolName) * 2.0;
   if(lastHighLevel > 0.0 && closeH1 > lastHighLevel + bosPadding)
     {
      AddStructureEvent(events, "BOS", "bullish", latestHighLabel, 1, iTime(symbolName, PERIOD_H1, 1), lastHighLevel);
      AppendLabelCsv(labelsCsv, "BOS");
      if(structureBias == "bearish")
        {
         AddStructureEvent(events, "CHOC", "bullish", latestHighLabel, 1, iTime(symbolName, PERIOD_H1, 1), lastHighLevel);
         AppendLabelCsv(labelsCsv, "CHOC");
        }
     }

   if(lastLowLevel > 0.0 && closeH1 < lastLowLevel - bosPadding)
     {
      AddStructureEvent(events, "BOS", "bearish", latestLowLabel, 1, iTime(symbolName, PERIOD_H1, 1), lastLowLevel);
      AppendLabelCsv(labelsCsv, "BOS");
      if(structureBias == "bullish")
        {
         AddStructureEvent(events, "CHOC", "bearish", latestLowLabel, 1, iTime(symbolName, PERIOD_H1, 1), lastLowLevel);
         AppendLabelCsv(labelsCsv, "CHOC");
        }
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AddOrMergeZoneCandidate(string symbolName, ZoneRecord &zones[], string kind, int originShift, datetime originTime, double originPrice, double bodyStart, bool fromZigZag, bool fromFractal)
  {
   for(int index = 0; index < ArraySize(zones); index++)
     {
      if(zones[index].kind != kind)
         continue;
      if(PriceDistancePoints(symbolName, zones[index].bodyStart, bodyStart) > ZoneMergeTolerancePoints)
         continue;

      if(fromZigZag)
         zones[index].zigzagCount++;
      if(fromFractal)
         zones[index].fractalCount++;

      int totalHits = MathMax(1, zones[index].zigzagCount + zones[index].fractalCount);
      zones[index].bodyStart = ((zones[index].bodyStart * (totalHits - 1)) + bodyStart) / totalHits;
      zones[index].originPrice = ((zones[index].originPrice * (totalHits - 1)) + originPrice) / totalHits;
      if(originShift > zones[index].originShift)
        {
         zones[index].originShift = originShift;
         zones[index].originTime = originTime;
        }
      return;
     }

   int count = ArraySize(zones);
   ArrayResize(zones, count + 1);
   zones[count].id = kind + "_" + IntegerToString((int)originTime);
   zones[count].timeframe = "5M";
   zones[count].anchorTimeframe = "1H";
   zones[count].kind = kind;
   zones[count].family = "temp";
   zones[count].status = "fresh";
   zones[count].strengthLabel = "";
   zones[count].modeBias = "neutral";
   zones[count].priceRelation = "unknown";
   zones[count].structureLabel = "";
   zones[count].strength = 0;
   zones[count].zigzagCount = fromZigZag ? 1 : 0;
   zones[count].fractalCount = fromFractal ? 1 : 0;
   zones[count].touchCount = 0;
   zones[count].retestCount = 0;
   zones[count].originShift = originShift;
   zones[count].originTime = originTime;
   zones[count].originPrice = originPrice;
   zones[count].bodyStart = bodyStart;
   zones[count].lower = bodyStart;
   zones[count].upper = bodyStart;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CollectZoneCandidates(string symbolName, ZoneRecord &zones[])
  {
   ArrayResize(zones, 0);

   for(int shift = MathMin(ScanBars, iBars(symbolName, PERIOD_H1) - 1); shift >= 2; shift--)
     {
      double zigzag = iCustom(symbolName, PERIOD_H1, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, shift);
      if(zigzag == 0.0)
         continue;

      bool isHigh = IsHighSwing(symbolName, PERIOD_H1, shift, zigzag);
      double candleOpen = iOpen(symbolName, PERIOD_H1, shift);
      double candleClose = iClose(symbolName, PERIOD_H1, shift);
      double bodyStart = isHigh ? MathMin(candleOpen, candleClose) : MathMax(candleOpen, candleClose);

      AddOrMergeZoneCandidate(symbolName, zones, isHigh ? "supply" : "demand", shift, iTime(symbolName, PERIOD_H1, shift), zigzag, bodyStart, true, false);
     }

   for(int shift2 = MathMin(ScanBars, iBars(symbolName, PERIOD_H1) - 1); shift2 >= 2; shift2--)
     {
      double fractalHigh = iFractals(symbolName, PERIOD_H1, MODE_UPPER, shift2);
      double fractalLow = iFractals(symbolName, PERIOD_H1, MODE_LOWER, shift2);
      double candleOpen = iOpen(symbolName, PERIOD_H1, shift2);
      double candleClose = iClose(symbolName, PERIOD_H1, shift2);

      if(fractalHigh > 0.0)
         AddOrMergeZoneCandidate(symbolName, zones, "supply", shift2, iTime(symbolName, PERIOD_H1, shift2), fractalHigh, MathMin(candleOpen, candleClose), false, true);

      if(fractalLow > 0.0)
         AddOrMergeZoneCandidate(symbolName, zones, "demand", shift2, iTime(symbolName, PERIOD_H1, shift2), fractalLow, MathMax(candleOpen, candleClose), false, true);
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void RefineZoneOnM5(string symbolName, ZoneRecord &zone)
  {
   double minThickness = ZoneThicknessMinPrice(symbolName, zone.family);
   double maxThickness = ZoneThicknessMaxPrice(symbolName, zone.family);
   int startShift = iBarShift(symbolName, PERIOD_M5, zone.originTime, false);
   if(startShift < 1)
      startShift = MathMin(BarsM5, iBars(symbolName, PERIOD_M5) - 1);

   double extreme = zone.bodyStart;
   zone.touchCount = 0;

   for(int shift = MathMin(startShift, iBars(symbolName, PERIOD_M5) - 1); shift >= 1; shift--)
     {
      double candleOpen = iOpen(symbolName, PERIOD_M5, shift);
      double candleClose = iClose(symbolName, PERIOD_M5, shift);
      double bodyEdge = zone.kind == "demand" ? MathMax(candleOpen, candleClose) : MathMin(candleOpen, candleClose);

      if(PriceDistancePoints(symbolName, bodyEdge, zone.bodyStart) > ZoneMergeTolerancePoints)
         continue;

      zone.touchCount++;
      if(zone.kind == "demand")
         extreme = MathMin(extreme, iLow(symbolName, PERIOD_M5, shift));
      else
         extreme = MathMax(extreme, iHigh(symbolName, PERIOD_M5, shift));
     }

   double thickness = zone.kind == "demand" ? zone.bodyStart - extreme : extreme - zone.bodyStart;
   if(zone.touchCount < MinimumM5Touches)
      thickness = minThickness;

   thickness = ClampDouble(MathMax(thickness, minThickness), minThickness, maxThickness);

   if(zone.kind == "demand")
     {
      zone.upper = zone.bodyStart;
      zone.lower = zone.bodyStart - thickness;
     }
   else
     {
      zone.lower = zone.bodyStart;
      zone.upper = zone.bodyStart + thickness;
     }

   zone.lower = NormalizePriceForSymbol(symbolName, zone.lower);
   zone.upper = NormalizePriceForSymbol(symbolName, zone.upper);
   zone.retestCount = CountRecentRetests(symbolName, PERIOD_M5, zone, 40);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void SortZonesByPriority(string symbolName, ZoneRecord &zones[])
  {
   double currentPrice = (MarketInfo(symbolName, MODE_BID) + MarketInfo(symbolName, MODE_ASK)) / 2.0;

   for(int outer = 0; outer < ArraySize(zones); outer++)
     {
      for(int inner = outer + 1; inner < ArraySize(zones); inner++)
        {
         double outerDistance = MathAbs(currentPrice - zones[outer].bodyStart);
         double innerDistance = MathAbs(currentPrice - zones[inner].bodyStart);
         bool swapNeeded = false;

         if(zones[inner].strength > zones[outer].strength)
            swapNeeded = true;
         else
            if(zones[inner].strength == zones[outer].strength && innerDistance < outerDistance)
               swapNeeded = true;

         if(swapNeeded)
           {
            ZoneRecord temp = zones[outer];
            zones[outer] = zones[inner];
            zones[inner] = temp;
           }
        }
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void LimitZonesPerSide(ZoneRecord &zones[])
  {
   ZoneRecord filtered[];
   int demandCount = 0;
   int supplyCount = 0;

   for(int index = 0; index < ArraySize(zones); index++)
     {
      bool isDemand = zones[index].kind == "demand";
      if(isDemand && demandCount >= MaxDemandZones)
         continue;
      if(!isDemand && supplyCount >= MaxSupplyZones)
         continue;

      int filteredCount = ArraySize(filtered);
      ArrayResize(filtered, filteredCount + 1);
      filtered[filteredCount] = zones[index];

      if(isDemand)
         demandCount++;
      else
         supplyCount++;
     }

   ArrayResize(zones, ArraySize(filtered));
   for(int copyIndex = 0; copyIndex < ArraySize(filtered); copyIndex++)
      zones[copyIndex] = filtered[copyIndex];
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void FinalizeZones(string symbolName, ZoneRecord &zones[], string structureBias)
  {
   double currentBid = MarketInfo(symbolName, MODE_BID);
   double currentAsk = MarketInfo(symbolName, MODE_ASK);
   double lastCloseM5 = iClose(symbolName, PERIOD_M5, 1);
   double invalidationPadding = SymbolPointSize(symbolName) * 4.0;

   for(int index = 0; index < ArraySize(zones); index++)
     {
      if(zones[index].zigzagCount <= 0)
        {
         zones[index].status = "deleted";
         continue;
        }

      zones[index].family = zones[index].fractalCount >= 1 ? "main" : "temp";

      if(zones[index].family == "main")
        {
         if(zones[index].fractalCount >= 2 && zones[index].zigzagCount >= 2)
            zones[index].strength = 3;
         else
            if(zones[index].fractalCount >= 1 && zones[index].zigzagCount >= 2)
               zones[index].strength = 2;
            else
               zones[index].strength = 1;
         zones[index].strengthLabel = "S" + IntegerToString(zones[index].strength);
        }
      else
        {
         zones[index].strength = 0;
         zones[index].strengthLabel = "TEMP";
        }

      RefineZoneOnM5(symbolName, zones[index]);

      if(zones[index].kind == "demand")
        {
         if(currentBid > zones[index].upper)
            zones[index].priceRelation = "above";
         else
            if(currentBid < zones[index].lower)
               zones[index].priceRelation = "below";
            else
               zones[index].priceRelation = "inside";

         if(lastCloseM5 < zones[index].lower - invalidationPadding)
            zones[index].status = zones[index].family == "temp" ? "deleted" : "invalidated";
         else
            if(CandleShowsReject(symbolName, PERIOD_M5, 1, zones[index]))
               zones[index].status = "rejected";
            else
               if(CandleShowsRespect(symbolName, PERIOD_M5, 1, zones[index]))
                  zones[index].status = "respected";
               else
                  zones[index].status = "active";

         zones[index].modeBias = (zones[index].priceRelation == "above" && zones[index].status != "deleted" && zones[index].status != "invalidated" && structureBias != "bearish") ? "buying" : "neutral";
        }
      else
        {
         if(currentAsk < zones[index].lower)
            zones[index].priceRelation = "below";
         else
            if(currentAsk > zones[index].upper)
               zones[index].priceRelation = "above";
            else
               zones[index].priceRelation = "inside";

         if(lastCloseM5 > zones[index].upper + invalidationPadding)
            zones[index].status = zones[index].family == "temp" ? "deleted" : "invalidated";
         else
            if(CandleShowsReject(symbolName, PERIOD_M5, 1, zones[index]))
               zones[index].status = "rejected";
            else
               if(CandleShowsRespect(symbolName, PERIOD_M5, 1, zones[index]))
                  zones[index].status = "respected";
               else
                  zones[index].status = "active";

         zones[index].modeBias = (zones[index].priceRelation == "below" && zones[index].status != "deleted" && zones[index].status != "invalidated" && structureBias != "bullish") ? "selling" : "neutral";
        }

      zones[index].structureLabel = structureBias;
     }

   SortZonesByPriority(symbolName, zones);
   LimitZonesPerSide(zones);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double ScoreZoneForExecution(string symbolName, ZoneRecord &zone, bool respect, bool reject, bool bosAligned, bool nearZone, bool biasAligned)
  {
   double score = zone.strength;
   if(zone.family == "temp")
      score += 0.6;
   if(zone.touchCount >= MinimumM5Touches)
      score += 0.4;
   if(nearZone)
      score += 0.6;
   if(respect)
      score += 0.6;
   if(reject)
      score += 0.6;
   if(bosAligned)
      score += 0.8;
   if(biasAligned)
      score += 0.4;
   if(zone.retestCount > 0)
      score += MathMin(zone.retestCount, 3) * 0.15;
   if(CurrentSpreadPoints(symbolName) > MaxSpreadPoints)
      score -= 1.0;
   return MathMax(score, 0.0);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void EvaluateExecutionPlan(string symbolName, ZoneRecord &zones[], string structureBias, ExecutionPlanRecord &plan)
  {
   ResetExecutionPlan(plan);

   int confirmationTf = TimeframeFromInput(AdvancedConfirmationTimeframe);
   double bosBullLevel = 0.0;
   double bosBearLevel = 0.0;
   bool bullishBos = DetectLowerTimeframeBos(symbolName, confirmationTf, true, bosBullLevel);
   bool bearishBos = DetectLowerTimeframeBos(symbolName, confirmationTf, false, bosBearLevel);

   for(int index = 0; index < ArraySize(zones); index++)
     {
      ZoneRecord zone = zones[index];
      if(zone.status == "deleted" || zone.status == "invalidated")
         continue;

      bool bullishSetup = zone.kind == "demand";
      string expectedBias = bullishSetup ? "buying" : "selling";
      bool biasAligned = zone.modeBias == expectedBias;
      double livePrice = bullishSetup ? MarketInfo(symbolName, MODE_ASK) : MarketInfo(symbolName, MODE_BID);
      double nearPadding = ZonePaddingPoints * SymbolPointSize(symbolName) * 0.35;
      bool nearZone = livePrice >= zone.lower - nearPadding && livePrice <= zone.upper + nearPadding;
      bool respect = CandleShowsRespect(symbolName, confirmationTf, 1, zone);
      bool reject = CandleShowsReject(symbolName, confirmationTf, 1, zone);
      bool bosAligned = bullishSetup ? bullishBos : bearishBos;
      int retests = CountRecentRetests(symbolName, confirmationTf, zone, 40);

      string rrrState = "none";
      if(retests > 0 && nearZone)
         rrrState = "retest";
      if(respect)
         rrrState = "respect";
      if(reject)
         rrrState = "reject";

      bool allowed = false;
      if(ExecutionStyle == "instant" || ExecutionStyle == "Instant" || ExecutionStyle == "INSTANT")
         allowed = nearZone && biasAligned;
      else
        {
         allowed = nearZone && biasAligned && (rrrState != "none" || bosAligned);
         if(AdvancedRetestLimit > 0 && retests > AdvancedRetestLimit)
            allowed = false;
         if((RetestEntryMode == "close" || RetestEntryMode == "Close" || RetestEntryMode == "CLOSE") && !respect && !reject)
            allowed = false;
        }

      double score = ScoreZoneForExecution(symbolName, zone, respect, reject, bosAligned, nearZone, biasAligned);
      if(score < plan.score)
         continue;

      plan.allowed = allowed;
      plan.prediction = bullishSetup ? "BUY" : "SELL";
      plan.style = ExecutionStyle;
      plan.confirmationTimeframe = TimeframeLabelByEnum(confirmationTf);
      plan.rrrState = rrrState;
      plan.bosDirection = bosAligned ? (bullishSetup ? "bullish" : "bearish") : "none";
      plan.reason = (allowed ? "Execution conditions satisfied." : "Execution conditions are not fully aligned.") + " Zone=" + zone.id + " bias=" + zone.modeBias + " status=" + zone.status;
      plan.activeZoneId = zone.id;
      plan.activeZoneKind = zone.kind;
      plan.zoneState = zone.status;
      plan.retestCount = retests;
      plan.score = score;
      plan.entryPrice = NormalizePriceForSymbol(symbolName, livePrice);

      double stopPadding = MathMax(SymbolPointSize(symbolName) * 8.0, ZonePaddingPoints * SymbolPointSize(symbolName) * 0.12);
      if(bullishSetup)
        {
         plan.stopLoss = NormalizePriceForSymbol(symbolName, zone.lower - stopPadding);
         plan.takeProfit = NormalizePriceForSymbol(symbolName, plan.entryPrice + ((plan.entryPrice - plan.stopLoss) * 2.0));
        }
      else
        {
         plan.stopLoss = NormalizePriceForSymbol(symbolName, zone.upper + stopPadding);
         plan.takeProfit = NormalizePriceForSymbol(symbolName, plan.entryPrice - ((plan.stopLoss - plan.entryPrice) * 2.0));
        }
     }

   if(plan.score <= 0.0 && structureBias != "neutral")
      plan.reason = "Structure is " + structureBias + " but no active zone is close enough for execution.";
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CopyZones(ZoneRecord &source[], ZoneRecord &target[])
  {
   ArrayResize(target, ArraySize(source));
   for(int index = 0; index < ArraySize(source); index++)
      target[index] = source[index];
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CopySwings(SwingRecord &source[], SwingRecord &target[])
  {
   ArrayResize(target, ArraySize(source));
   for(int index = 0; index < ArraySize(source); index++)
      target[index] = source[index];
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CopyEvents(StructureEventRecord &source[], StructureEventRecord &target[])
  {
   ArrayResize(target, ArraySize(source));
   for(int index = 0; index < ArraySize(source); index++)
      target[index] = source[index];
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool SymbolHasRequiredHistory(string symbolName)
  {
   if(iBars(symbolName, PERIOD_H1) < BarsH1)
      return false;
   if(iBars(symbolName, PERIOD_M5) < BarsM5)
      return false;
   if(iBars(symbolName, PERIOD_M1) < BarsM1)
      return false;
   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool AnalyzeSymbolState(string symbolName, ZoneRecord &zones[], SwingRecord &swings[], StructureEventRecord &events[], string &structureBias, string &labelsCsv, ExecutionPlanRecord &plan)
  {
   ResetExecutionPlan(plan);
   if(!SymbolHasRequiredHistory(symbolName))
      return false;

   CollectH1Structure(symbolName, swings, events, structureBias, labelsCsv);
   CollectZoneCandidates(symbolName, zones);
   FinalizeZones(symbolName, zones, structureBias);
   EvaluateExecutionPlan(symbolName, zones, structureBias, plan);
   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ClearZoneObjects()
  {
   for(int index = ObjectsTotal() - 1; index >= 0; index--)
     {
      string name = ObjectName(index);
      if(StringFind(name, ZonePrefix, 0) == 0)
         ObjectDelete(name);
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
color ZoneColor(ZoneRecord &zone)
  {
   if(zone.kind == "demand")
      return zone.family == "main" ? DemandColor : SupportColor;
   return zone.family == "main" ? SupplyColor : ResistanceColor;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string ZoneLabel(ZoneRecord &zone)
  {
   string label = zone.anchorTimeframe + " ";
   label += zone.family == "main" ? "MAIN " : "TEMP ";
   label += zone.kind + " " + zone.strengthLabel + " " + zone.status;
   if(zone.modeBias != "neutral")
      label += " " + zone.modeBias;
   return label;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawZoneRectangle(string name, datetime leftTime, datetime rightTime, double upper, double lower, color zoneColor, string label)
  {
   if(ObjectFind(name) == -1)
      ObjectCreate(name, OBJ_RECTANGLE, 0, leftTime, upper, rightTime, lower);
   else
     {
      ObjectMove(name, 0, leftTime, upper);
      ObjectMove(name, 1, rightTime, lower);
     }

   ObjectSet(name, OBJPROP_COLOR, zoneColor);
   ObjectSet(name, OBJPROP_WIDTH, 1);
   ObjectSet(name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSet(name, OBJPROP_BACK, true);

   string labelName = name + "_LABEL";
   if(ObjectFind(labelName) == -1)
      ObjectCreate(labelName, OBJ_TEXT, 0, leftTime, upper);
   else
      ObjectMove(labelName, 0, leftTime, upper);

   ObjectSetText(labelName, label, 8, "Arial", zoneColor);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawTextMarker(string name, datetime markerTime, double markerPrice, string label, color markerColor, int fontSize)
  {
   if(ObjectFind(name) == -1)
      ObjectCreate(name, OBJ_TEXT, 0, markerTime, markerPrice);
   else
      ObjectMove(name, 0, markerTime, markerPrice);

   ObjectSetText(name, label, fontSize, "Arial", markerColor);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawCornerLabel(string name, string label, color labelColor)
  {
   if(ObjectFind(name) == -1)
      ObjectCreate(name, OBJ_LABEL, 0, 0, 0);

   ObjectSet(name, OBJPROP_CORNER, 0);
   ObjectSet(name, OBJPROP_XDISTANCE, 10);
   ObjectSet(name, OBJPROP_YDISTANCE, 15);
   ObjectSetText(name, label, 9, "Arial", labelColor);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawSwingMarkers()
  {
   if(!DrawStructureLabels)
      return;

   double offset = MathMax(SymbolPointSize(Symbol()) * 8.0, ZonePaddingPoints * SymbolPointSize(Symbol()) * 0.10);

   for(int index = 0; index < ArraySize(g_chartSwings); index++)
     {
      string objectName = ZonePrefix + Symbol() + "_SWING_" + IntegerToString(index);
      color markerColor = g_chartSwings[index].isHigh ? SupplyColor : DemandColor;
      DrawTextMarker(
         objectName,
         g_chartSwings[index].swingTime,
         g_chartSwings[index].price + (g_chartSwings[index].isHigh ? offset : -offset),
         (g_chartSwings[index].fromZigZag ? "ZZ " : "FR ") + g_chartSwings[index].label,
         markerColor,
         8
      );
     }

   for(int eventIndex = 0; eventIndex < ArraySize(g_chartEvents); eventIndex++)
     {
      string objectName2 = ZonePrefix + Symbol() + "_EVENT_" + IntegerToString(eventIndex);
      color markerColor2 = g_chartEvents[eventIndex].direction == "bullish" ? DemandColor : SupplyColor;
      DrawTextMarker(objectName2, g_chartEvents[eventIndex].eventTime, g_chartEvents[eventIndex].level, g_chartEvents[eventIndex].eventName + " " + g_chartEvents[eventIndex].structureLabel, markerColor2, 8);
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawChartZones()
  {
   if(!DrawZonesOnChart)
      return;

   ClearZoneObjects();

   int chartSeconds = TimeframeSeconds(Period());
   datetime rightTime = Time[0] + (chartSeconds * ZoneProjectionBars);

   for(int zoneIndex = 0; zoneIndex < ArraySize(g_chartZones); zoneIndex++)
     {
      string objectName = ZonePrefix + Symbol() + "_ZONE_" + g_chartZones[zoneIndex].family + "_" + g_chartZones[zoneIndex].kind + "_" + IntegerToString(zoneIndex);
      DrawZoneRectangle(objectName, g_chartZones[zoneIndex].originTime, rightTime, g_chartZones[zoneIndex].upper, g_chartZones[zoneIndex].lower, ZoneColor(g_chartZones[zoneIndex]), ZoneLabel(g_chartZones[zoneIndex]));
     }

   DrawSwingMarkers();

   string summary = "ZONES " + Symbol() + " | bias " + g_structureBias + " | zones " + IntegerToString(ArraySize(g_chartZones)) + " | exec " + (g_executionPlan.allowed ? "ON " : "OFF ") + g_executionPlan.prediction + " " + g_executionPlan.style;
   if(g_aiBridge.available && g_aiBridge.prediction != "")
      summary += " | AI " + g_aiBridge.prediction + " " + DoubleToString(g_aiBridge.confidence, 2);
   else
      if(g_lastBridgeError != "")
         summary += " | bridge " + g_lastBridgeError;

   DrawCornerLabel(ZonePrefix + "SUMMARY", summary, g_executionPlan.allowed ? clrWhite : clrSilver);
   ChartRedraw();
  }

// ============================================================
// PAYLOAD BUILDING
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string CandleJsonForSymbol(string symbolName, int timeframe, int shift)
  {
   int digits = SymbolDigitsValue(symbolName);
   datetime barTime = iTime(symbolName, timeframe, shift);

   return StringFormat(
             "{\"timestamp\":\"%s\",\"open\":%s,\"high\":%s,\"low\":%s,\"close\":%s,\"volume\":%.2f}",
             TimeToString(barTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             DoubleToString(iOpen(symbolName, timeframe, shift), digits),
             DoubleToString(iHigh(symbolName, timeframe, shift), digits),
             DoubleToString(iLow(symbolName, timeframe, shift), digits),
             DoubleToString(iClose(symbolName, timeframe, shift), digits),
             iVolume(symbolName, timeframe, shift)
          );
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string TimeframeSeriesForSymbol(string symbolName, string label, int timeframe, int bars)
  {
   string result = "\"" + label + "\":[";
   bool first = true;

   for(int shift = bars - 1; shift >= 0; shift--)
     {
      if(iTime(symbolName, timeframe, shift) == 0)
         continue;

      if(!first)
         result += ",";

      result += CandleJsonForSymbol(symbolName, timeframe, shift);
      first = false;
     }

   result += "]";
   return result;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string BuildAccountJson()
  {
   string account = "{";
   account += "\"account_id\":\"" + IntegerToString(AccountNumber()) + "\",";
   account += "\"name\":\"" + EscapeJson(AccountName()) + "\",";
   account += "\"server\":\"" + EscapeJson(AccountServer()) + "\",";
   account += "\"company\":\"" + EscapeJson(AccountCompany()) + "\",";
   account += "\"currency\":\"" + EscapeJson(AccountCurrency()) + "\",";
   account += "\"leverage\":" + IntegerToString(AccountLeverage()) + ",";
   account += "\"balance\":" + DoubleToString(AccountBalance(), 2) + ",";
   account += "\"equity\":" + DoubleToString(AccountEquity(), 2) + ",";
   account += "\"free_margin\":" + DoubleToString(AccountFreeMargin(), 2) + ",";
   account += "\"margin\":" + DoubleToString(AccountMargin(), 2) + ",";
   account += "\"daily_pnl\":" + DoubleToString(AccountProfit(), 2) + ",";
   account += "\"open_positions\":" + IntegerToString(OrdersTotal()) + ",";
   account += "\"risk_exposure_pct\":" + DoubleToString(AccountEquity() > 0 ? (AccountMargin() / AccountEquity()) * 100.0 : 0.0, 2) + ",";
   account += "\"status\":\"live-feed\"";
   account += "}";
   return account;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string BuildPositionsJson()
  {
   string json = "[";
   bool first = true;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(IncludeOnlyMagicPositionsInPayload && OrderMagicNumber() != MagicNumber)
         continue;

      string orderSymbol = OrderSymbol();
      int digits = SymbolDigitsValue(orderSymbol);

      if(!first)
         json += ",";

      json += "{";
      json += "\"ticket\":" + IntegerToString(OrderTicket()) + ",";
      json += "\"symbol\":\"" + EscapeJson(orderSymbol) + "\",";
      json += "\"type\":" + IntegerToString(OrderType()) + ",";
      json += "\"lots\":" + DoubleToString(OrderLots(), 2) + ",";
      json += "\"open_price\":" + DoubleToString(OrderOpenPrice(), digits) + ",";
      json += "\"sl\":" + DoubleToString(OrderStopLoss(), digits) + ",";
      json += "\"tp\":" + DoubleToString(OrderTakeProfit(), digits) + ",";
      json += "\"profit\":" + DoubleToString(OrderProfit(), 2) + ",";
      json += "\"magic\":" + IntegerToString(OrderMagicNumber());
      json += "}";
      first = false;
     }

   json += "]";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string JsonArrayFromCsv(string csvValues)
  {
   if(csvValues == "")
      return "[]";

   string parts[];
   int total = StringSplit(csvValues, ',', parts);
   string json = "[";

   for(int index = 0; index < total; index++)
     {
      string part = parts[index];
      StringTrimLeft(part);
      StringTrimRight(part);
      if(part == "")
         continue;

      if(json != "[")
         json += ",";
      json += "\"" + EscapeJson(part) + "\"";
     }

   json += "]";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string SwingsJson(string symbolName, SwingRecord &swings[])
  {
   string json = "[";
   int digits = SymbolDigitsValue(symbolName);

   for(int index = 0; index < ArraySize(swings); index++)
     {
      if(json != "[")
         json += ",";

      json += "{";
      json += "\"timeframe\":\"1H\",";
      json += "\"shift\":" + IntegerToString(swings[index].shift) + ",";
      json += "\"timestamp\":\"" + TimeToString(swings[index].swingTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "\",";
      json += "\"price\":" + DoubleToString(swings[index].price, digits) + ",";
      json += "\"kind\":\"" + (swings[index].isHigh ? "high" : "low") + "\",";
      json += "\"source\":\"" + (swings[index].fromZigZag ? "zigzag" : "fractal") + "\",";
      json += "\"label\":\"" + EscapeJson(swings[index].label) + "\"";
      json += "}";
     }

   json += "]";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string EventsJson(string symbolName, StructureEventRecord &events[])
  {
   string json = "[";
   int digits = SymbolDigitsValue(symbolName);

   for(int index = 0; index < ArraySize(events); index++)
     {
      if(json != "[")
         json += ",";

      json += "{";
      json += "\"event\":\"" + EscapeJson(events[index].eventName) + "\",";
      json += "\"direction\":\"" + EscapeJson(events[index].direction) + "\",";
      json += "\"structure_label\":\"" + EscapeJson(events[index].structureLabel) + "\",";
      json += "\"level\":" + DoubleToString(events[index].level, digits) + ",";
      json += "\"origin_shift\":" + IntegerToString(events[index].originShift) + ",";
      json += "\"timestamp\":\"" + TimeToString(events[index].eventTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "\"";
      json += "}";
     }

   json += "]";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string ZonesJson(string symbolName, ZoneRecord &zones[])
  {
   string json = "[";
   int digits = SymbolDigitsValue(symbolName);

   for(int index = 0; index < ArraySize(zones); index++)
     {
      if(json != "[")
         json += ",";

      json += "{";
      json += "\"id\":\"" + EscapeJson(zones[index].id) + "\",";
      json += "\"timeframe\":\"" + zones[index].timeframe + "\",";
      json += "\"anchor_timeframe\":\"" + zones[index].anchorTimeframe + "\",";
      json += "\"kind\":\"" + zones[index].kind + "\",";
      json += "\"family\":\"" + zones[index].family + "\",";
      json += "\"strength\":" + IntegerToString(zones[index].strength) + ",";
      json += "\"strength_label\":\"" + EscapeJson(zones[index].strengthLabel) + "\",";
      json += "\"lower\":" + DoubleToString(zones[index].lower, digits) + ",";
      json += "\"upper\":" + DoubleToString(zones[index].upper, digits) + ",";
      json += "\"body_start\":" + DoubleToString(zones[index].bodyStart, digits) + ",";
      json += "\"origin_index\":" + IntegerToString(zones[index].originShift) + ",";
      json += "\"origin_time\":\"" + TimeToString(zones[index].originTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "\",";
      json += "\"origin_price\":" + DoubleToString(zones[index].originPrice, digits) + ",";
      json += "\"zigzag_count\":" + IntegerToString(zones[index].zigzagCount) + ",";
      json += "\"fractal_count\":" + IntegerToString(zones[index].fractalCount) + ",";
      json += "\"touch_count\":" + IntegerToString(zones[index].touchCount) + ",";
      json += "\"retest_count\":" + IntegerToString(zones[index].retestCount) + ",";
      json += "\"status\":\"" + EscapeJson(zones[index].status) + "\",";
      json += "\"mode_bias\":\"" + EscapeJson(zones[index].modeBias) + "\",";
      json += "\"price_relation\":\"" + EscapeJson(zones[index].priceRelation) + "\",";
      json += "\"structure_label\":\"" + EscapeJson(zones[index].structureLabel) + "\"";
      json += "}";
     }

   json += "]";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string ExecutionDecisionJson(string symbolName, ExecutionPlanRecord &plan, string structureBias)
  {
   int digits = SymbolDigitsValue(symbolName);
   string direction = "neutral";
   if(plan.prediction == "BUY")
      direction = "long";
   else
      if(plan.prediction == "SELL")
         direction = "short";

   string json = "{";
   json += "\"allowed\":" + BoolText(plan.allowed) + ",";
   json += "\"direction\":\"" + direction + "\",";
   json += "\"timeframe\":\"" + EscapeJson(plan.confirmationTimeframe) + "\",";
   json += "\"score\":" + DoubleToString(plan.score, 2) + ",";
   json += "\"rationale\":\"" + EscapeJson(plan.reason) + "\",";
   json += "\"entry\":" + DoubleToString(plan.entryPrice, digits) + ",";
   json += "\"stop_loss\":" + DoubleToString(plan.stopLoss, digits) + ",";
   json += "\"take_profit\":" + DoubleToString(plan.takeProfit, digits) + ",";
   json += "\"style\":\"" + EscapeJson(plan.style) + "\",";
   json += "\"active_zone_id\":\"" + EscapeJson(plan.activeZoneId) + "\",";
   json += "\"active_zone_kind\":\"" + EscapeJson(plan.activeZoneKind) + "\",";
   json += "\"rrr_state\":\"" + EscapeJson(plan.rrrState) + "\",";
   json += "\"bos_direction\":\"" + EscapeJson(plan.bosDirection) + "\",";
   json += "\"structure_bias\":\"" + EscapeJson(structureBias) + "\"";
   json += "}";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string ExecutionContextJson(string symbolName, ExecutionPlanRecord &plan)
  {
   int digits = SymbolDigitsValue(symbolName);
   string json = "{";
   json += "\"supported_styles\":[\"instant\",\"advanced\"],";
   json += "\"configured_style\":\"" + EscapeJson(plan.style) + "\",";
   json += "\"confirmation_timeframe\":\"" + EscapeJson(plan.confirmationTimeframe) + "\",";
   json += "\"retest_limit\":" + IntegerToString(AdvancedRetestLimit) + ",";
   json += "\"retest_entry_mode\":\"" + EscapeJson(RetestEntryMode) + "\",";
   json += "\"rrr_state\":\"" + EscapeJson(plan.rrrState) + "\",";
   json += "\"bos_direction\":\"" + EscapeJson(plan.bosDirection) + "\",";
   json += "\"local_prediction\":\"" + EscapeJson(plan.prediction) + "\",";
   json += "\"local_allowed\":" + BoolText(plan.allowed) + ",";
   json += "\"reason\":\"" + EscapeJson(plan.reason) + "\",";
   json += "\"active_zone_id\":\"" + EscapeJson(plan.activeZoneId) + "\",";
   json += "\"active_zone_kind\":\"" + EscapeJson(plan.activeZoneKind) + "\",";
   json += "\"zone_state\":\"" + EscapeJson(plan.zoneState) + "\",";
   json += "\"retest_count\":" + IntegerToString(plan.retestCount) + ",";
   json += "\"entry\":" + DoubleToString(plan.entryPrice, digits) + ",";
   json += "\"stop_loss\":" + DoubleToString(plan.stopLoss, digits) + ",";
   json += "\"take_profit\":" + DoubleToString(plan.takeProfit, digits);
   json += "}";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string IndicatorValuesJson(string symbolName)
  {
   int digits = SymbolDigitsValue(symbolName);
   string json = "{";
   json += "\"atr_h1\":" + DoubleToString(iATR(symbolName, PERIOD_H1, 14, 1), digits) + ",";
   json += "\"atr_m5\":" + DoubleToString(iATR(symbolName, PERIOD_M5, 14, 1), digits) + ",";
   json += "\"spread_points\":" + DoubleToString(CurrentSpreadPoints(symbolName), 1);
   json += "}";
   return json;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string BuildPayloadForSymbol(string symbolName)
  {
   ZoneRecord localZones[];
   SwingRecord localSwings[];
   StructureEventRecord localEvents[];
   ExecutionPlanRecord localPlan;
   string structureBias = "neutral";
   string labelsCsv = "";

   if(!AnalyzeSymbolState(symbolName, localZones, localSwings, localEvents, structureBias, labelsCsv, localPlan))
      return "";

   string account = BuildAccountJson();
   string timeframes = "{"
                       + TimeframeSeriesForSymbol(symbolName, "1H", PERIOD_H1, BarsH1) + ","
                       + TimeframeSeriesForSymbol(symbolName, "5M", PERIOD_M5, BarsM5) + ","
                       + TimeframeSeriesForSymbol(symbolName, "1M", PERIOD_M1, BarsM1)
                       + "}";

   string payload = "{";
   payload += "\"source\":\"mt4-websocket\",";
   payload += "\"symbol\":\"" + EscapeJson(symbolName) + "\",";
   payload += "\"timeframe\":\"5M\",";
   payload += "\"broker\":\"" + EscapeJson(AccountCompany()) + "\",";
   payload += "\"terminal_time\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "\",";
   payload += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "\",";
   payload += "\"spread_points\":" + IntegerToString((int)MarketInfo(symbolName, MODE_SPREAD)) + ",";
   payload += "\"account\":" + account + ",";
   payload += "\"positions\":" + BuildPositionsJson() + ",";
   payload += "\"news\":[],";
   payload += "\"chart_data\":" + timeframes + ",";
   payload += "\"timeframes\":" + timeframes + ",";
   payload += "\"market_structure\":{";
   payload += "\"checkpoint_timeframe\":\"1H\",";
   payload += "\"refinement_timeframe\":\"5M\",";
   payload += "\"bias\":\"" + EscapeJson(structureBias) + "\",";
   payload += "\"labels\":" + JsonArrayFromCsv(labelsCsv) + ",";
   payload += "\"swings\":" + SwingsJson(symbolName, localSwings) + ",";
   payload += "\"events\":" + EventsJson(symbolName, localEvents);
   payload += "},";
   payload += "\"zones\":" + ZonesJson(symbolName, localZones) + ",";
   payload += "\"execution_context\":" + ExecutionContextJson(symbolName, localPlan) + ",";
   payload += "\"execution_decision\":" + ExecutionDecisionJson(symbolName, localPlan, structureBias) + ",";
   payload += "\"indicator_values\":" + IndicatorValuesJson(symbolName) + ",";
   payload += "\"bridge\":{";
   payload += "\"transport\":\"websocket\",";
   payload += "\"bridge_enabled\":" + BoolText(EnableBridgePosting) + ",";
   payload += "\"last_bridge_success\":\"" + (g_lastBridgeSuccess > 0 ? TimeToString(g_lastBridgeSuccess, TIME_DATE | TIME_MINUTES | TIME_SECONDS) : "") + "\",";
   payload += "\"last_bridge_error\":\"" + EscapeJson(g_lastBridgeError) + "\",";
   payload += "\"bridge_failures\":" + IntegerToString(g_bridgeFailureCount);
   payload += "}";
   payload += "}";
   return payload;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void UpdateAiBridgeState(string reply)
  {
   g_aiBridge.raw = reply;
   g_aiBridge.available = JsonValue(reply, "status") == "ok";
   g_aiBridge.prediction = JsonValue(reply, "ai_prediction");
   g_aiBridge.confidence = StrToDouble(JsonValue(reply, "ai_confidence"));
   g_aiBridge.reason = JsonValue(reply, "ai_reason");
   g_aiBridge.zoneState = JsonValue(reply, "ai_zone_confirmation");
   g_aiBridge.executionHint = JsonValue(reply, "ai_execution_hint");
   g_aiBridge.riskHint = JsonValue(reply, "ai_risk_hint");
   g_aiBridge.modelStatus = JsonValue(reply, "ai_model_status");
   g_aiBridge.receivedAt = TimeCurrent();
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void PostSnapshotForSymbol(string symbolName)
  {
   if(!SymbolHasRequiredHistory(symbolName))
     {
      Print("ZONES skipped ", symbolName, " because timeframe history is not loaded yet.");
      return;
     }

   string payload = BuildPayloadForSymbol(symbolName);
   if(payload == "")
      return;
   if(!EnableBridgePosting)
      return;

   string request =
      "{"
      "\"action\":\"post_snapshot\","
      "\"account_id\":\"" + EscapeJson(TerminalAccountId()) + "\","
      "\"symbol\":\"" + EscapeJson(symbolName) + "\","
      "\"payload\":" + payload +
      "}";

   string reply = "";
   if(!WsRequest(request, reply))
     {
      Print("ZONES bridge post failed for ", symbolName, ". Local analysis remains active.");
      return;
     }

   if(symbolName == Symbol())
      UpdateAiBridgeState(reply);

   if(JsonValue(reply, "status") != "ok")
      Print("ZONES bridge rejected snapshot for ", symbolName, " reply=", reply);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void PostSnapshots()
  {
   if(!PostAllMarketWatchSymbols)
     {
      PostSnapshotForSymbol(Symbol());
      return;
     }

   int totalSymbols = SymbolsTotal(true);
   int processed = 0;

   for(int index = 0; index < totalSymbols; index++)
     {
      string symbolName = SymbolName(index, true);
      if(symbolName == "")
         continue;

      PostSnapshotForSymbol(symbolName);
      processed++;

      if(MaxMarketWatchSymbols > 0 && processed >= MaxMarketWatchSymbols)
         break;
     }
  }

// ============================================================
// LIFECYCLE
// ============================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool AutoExecutionAllowed()
  {
   if(!EnableAutoExecution)
      return false;
   if(!g_executionPlan.allowed)
      return false;
   if(InTradeCooldown())
      return false;

   if(RequireAiAgreementForAutoExecution)
     {
      if(!g_aiBridge.available)
         return false;
      if(g_executionPlan.prediction == "BUY" && g_aiBridge.prediction != "BUY")
         return false;
      if(g_executionPlan.prediction == "SELL" && g_aiBridge.prediction != "SELL")
         return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ExecuteAutoTradeIfNeeded()
  {
   if(!AutoExecutionAllowed())
      return;

   string symbolName = Symbol();
   int orderType = g_executionPlan.prediction == "BUY" ? OP_BUY : OP_SELL;
   double price = orderType == OP_BUY ? NormalizePriceForSymbol(symbolName, MarketInfo(symbolName, MODE_ASK)) : NormalizePriceForSymbol(symbolName, MarketInfo(symbolName, MODE_BID));
   double lots = NormalizeLotsForSymbol(symbolName, AutoExecutionLots);
   double sl = NormalizePriceForSymbol(symbolName, g_executionPlan.stopLoss);
   double tp = NormalizePriceForSymbol(symbolName, g_executionPlan.takeProfit);
   string rejectReason = "";

   if(!PreTradeCheck("auto", symbolName, orderType, lots, price, sl, tp, rejectReason))
     {
      Print("ZONES auto execution blocked: ", rejectReason);
      return;
     }

   int ticket = OrderSend(symbolName, orderType, lots, price, MaxSlippage, sl, tp, "ZONES_AUTO_" + g_executionPlan.activeZoneId, MagicNumber, 0, clrNONE);
   if(ticket < 0)
     {
      Print("ZONES auto execution failed: ", ErrorDescriptionEx(GetLastError()));
      return;
     }

   g_lastTradeTime = TimeCurrent();
   Print("ZONES auto execution opened ticket=", ticket, " prediction=", g_executionPlan.prediction, " zone=", g_executionPlan.activeZoneId);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void RefreshChartState()
  {
   ZoneRecord localZones[];
   SwingRecord localSwings[];
   StructureEventRecord localEvents[];
   ExecutionPlanRecord localPlan;
   string localBias = "neutral";
   string localLabels = "";

   ResetExecutionPlan(localPlan);
   if(!AnalyzeSymbolState(Symbol(), localZones, localSwings, localEvents, localBias, localLabels, localPlan))
     {
      ArrayResize(g_chartZones, 0);
      ArrayResize(g_chartSwings, 0);
      ArrayResize(g_chartEvents, 0);
      g_structureBias = "neutral";
      g_structureLabelsCsv = "";
      g_executionPlan = localPlan;
      return;
     }

   CopyZones(localZones, g_chartZones);
   CopySwings(localSwings, g_chartSwings);
   CopyEvents(localEvents, g_chartEvents);
   g_structureBias = localBias;
   g_structureLabelsCsv = localLabels;
   g_executionPlan = localPlan;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void RunBridgeCycle(bool includeAllSymbols)
  {
   RefreshChartState();
   DrawChartZones();
   ExecuteAutoTradeIfNeeded();

   if(includeAllSymbols && EnableBridgePosting)
      PostSnapshots();
   else
      if(EnableBridgePosting)
         PostSnapshotForSymbol(Symbol());

   if(EnableBridgePosting)
      PollCommands();
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(TimerSeconds);
   g_aiBridge.available = false;

   if(EnableBridgePosting)
     {
      string healthReply = "";
      if(WsRequest("{\"action\":\"health\"}", healthReply))
         Print("ZONES bridge ready. Health=", healthReply);
      else
         Print("ZONES bridge unavailable at startup. EA will continue with local-only analysis.");
     }

   RunBridgeCycle(false);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ClearZoneObjects();
   g_ws.Close();
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTimer()
  {
   RunBridgeCycle(true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTick()
  {
   static datetime lastBarTime = 0;

   if(Time[0] != lastBarTime)
     {
      lastBarTime = Time[0];
      RunBridgeCycle(false);
     }
  }
//+------------------------------------------------------------------+
