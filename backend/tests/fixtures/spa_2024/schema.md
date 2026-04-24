# Spa 2024 Race — DataFrame Schemas

## TimingData
Rows: 53040
```
SessionKey                                 int64
timestamp                        timedelta64[us]
DriverNo                                     str
GapToLeader                                  str
IntervalToPositionAhead_Value                str
                                      ...       
Sectors_0_OverallFastest                  object
Sectors_0_PersonalFastest                 object
Sectors_0_PreviousValue                      str
BestLapTime_Lap                          float64
NumberOfPitStops                         float64
Length: 99, dtype: object
```

Head (3 rows):
```
   SessionKey              timestamp  ... BestLapTime_Lap NumberOfPitStops
0        9574 0 days 00:00:03.734000  ...             NaN              NaN
1        9574 0 days 00:00:03.734000  ...             NaN              NaN
2        9574 0 days 00:00:03.734000  ...             NaN              NaN

[3 rows x 99 columns]
```

## Position.z
Rows: 625020
```
SessionKey              int64
timestamp     timedelta64[us]
Utc                       str
DriverNo                  str
Status                    str
X                       int64
Y                       int64
Z                       int64
dtype: object
```

Head (3 rows):
```
   SessionKey              timestamp                           Utc  ...  X  Y  Z
0        9574 0 days 00:01:45.570000  2024-07-28T12:10:22.7877313Z  ...  0  0  0
1        9574 0 days 00:01:45.570000  2024-07-28T12:10:22.7877313Z  ...  0  0  0
2        9574 0 days 00:01:45.570000  2024-07-28T12:10:22.7877313Z  ...  0  0  0

[3 rows x 8 columns]
```

## RaceControlMessages
Rows: 21
```
SessionKey              int64
timestamp     timedelta64[us]
Utc                       str
Lap                     int64
Category                  str
Flag                      str
Scope                     str
Message                   str
Status                    str
Sector                float64
dtype: object
```

Head (3 rows):
```
   SessionKey              timestamp  ... Status  Sector
0        9574 0 days 00:11:22.797000  ...    NaN     NaN
1        9574 0 days 00:21:22.802000  ...    NaN     NaN
2        9574 0 days 00:36:35.185000  ...    NaN     NaN

[3 rows x 10 columns]
```

## WeatherData
Rows: 137
```
SessionKey                 int64
timestamp        timedelta64[us]
AirTemp                      str
Humidity                     str
Pressure                     str
Rainfall                     str
TrackTemp                    str
WindDirection                str
WindSpeed                    str
dtype: object
```

Head (3 rows):
```
   SessionKey              timestamp AirTemp  ... TrackTemp WindDirection WindSpeed
0        9574 0 days 00:00:14.052000    21.0  ...      42.1           217       0.5
1        9574 0 days 00:01:14.050000    20.6  ...      42.1             0       1.1
2        9574 0 days 00:02:14.047000    20.6  ...      42.2           284       0.7

[3 rows x 9 columns]
```

## SessionData
Rows: 51
```
session_key        int64
Utc                  str
Lap              float64
TrackStatus          str
SessionStatus        str
dtype: object
```

Head (3 rows):
```
   session_key                       Utc  Lap TrackStatus SessionStatus
0         9574  2024-07-28T12:09:48.568Z  1.0         NaN           NaN
1         9574   2024-07-28T12:12:23.39Z  NaN    AllClear           NaN
2         9574  2024-07-28T13:03:52.741Z  NaN         NaN       Started
```

## DriverList
Rows: 20
```
RacingNumber       str
BroadcastName      str
FullName           str
Tla                str
Line             int64
TeamName           str
TeamColour         str
FirstName          str
LastName           str
Reference          str
HeadshotUrl        str
CountryCode        str
NameFormat         str
dtype: object
```

Head (3 rows):
```
  RacingNumber BroadcastName  ... CountryCode NameFormat
0           16     C LECLERC  ...         MON        NaN
1           11       S PEREZ  ...         MEX        NaN
2           44    L HAMILTON  ...         GBR        NaN

[3 rows x 13 columns]
```
