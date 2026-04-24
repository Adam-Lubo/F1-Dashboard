// shared-types/src/index.ts

export type SessionState =
  | "IDLE" | "ARMED" | "LIVE" | "PAUSED"
  | "RED_FLAG" | "YELLOW_FLAG" | "SC" | "VSC" | "ENDED";

export type SessionType =
  | "PRACTICE" | "QUALIFYING" | "SPRINT_QUALI" | "SPRINT" | "RACE";

export type TireCompound = "S" | "M" | "H" | "I" | "W";

export interface SessionInfo {
  state: SessionState;
  session_type: SessionType | null;
  session_name: string;
  round: number;
  season: number;
  current_lap: number | null;
  total_laps: number | null;
  leader_gap: string | null;
  countdown_seconds: number | null;
  session_elapsed_seconds: number | null;
}

export interface TimingEntry {
  position: number;
  driver_code: string;
  team_id: string;
  last_lap: string | null;
  gap: string | null;
  interval: string | null;
  tire: TireCompound | null;
  tire_age: number | null;
  is_fastest_overall: boolean;
  is_personal_best: boolean;
  is_in_battle: boolean;
  is_retired: boolean;
  dnf: boolean;
  // Note: `is_watchlisted` is computed frontend-side from localStorage — not on the wire.
}

export interface TimingTower {
  entries: TimingEntry[];
  fastest_lap_driver: string | null;
  fastest_lap_time: string | null;
  updated_at: number;
}

export interface DriverPosition {
  driver_code: string;
  team_id: string;
  x: number;
  y: number;
}

export interface TrackPositions {
  drivers: DriverPosition[];
  updated_at: number;
}

export interface WeatherData {
  air_temp: number;
  track_temp: number | null;
  humidity: number;
  wind_speed: number;
  rain_chance: number;
  description: string;
  is_live: boolean;
  updated_at: number;
}

export interface DriverStanding {
  position: number;
  driver_code: string;
  team_id: string;
  points: number;
  wins: number;
}

export interface ConstructorStanding {
  position: number;
  team_id: string;
  team_name: string;
  points: number;
  wins: number;
}

export interface HistoricalStats {
  driver_code: string;
  circuit: string;
  best_finish: number | null;
  best_quali: number | null;
  avg_race_pos: number | null;
  avg_quali_pos: number | null;
  wins: number;
  poles: number;
  races: number;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  published_at: string;
  summary: string | null;
}

export interface ScheduleSession {
  type: SessionType;
  name: string;
  day: string;
  local_time: string;
  utc_time: string;
  is_next: boolean;
  is_complete: boolean;
}

export interface WeekendSchedule {
  circuit: string;
  country: string;
  round: number;
  season: number;
  sessions: ScheduleSession[];
}

export interface PredictionEntry {
  position: number;
  driver_code: string;
  team_id: string;
  win_probability: number;
}

export interface Predictions {
  entries: PredictionEntry[];
  model: string;
  updated_at: number;
}

export interface ReplayStatus {
  active: boolean;
  session_key: string | null;
  current_lap: number;
  total_laps: number;
}

export interface StartingGridEntry {
  position: number;
  driver_code: string;
  team_id: string;
  quali_time: string | null;
}

export interface StartingGrid {
  circuit: string;
  entries: StartingGridEntry[];
  updated_at: number;
}

export type RaceControlCategory =
  | "Flag" | "SafetyCar" | "Drs" | "CarEvent" | "Other";

export interface RaceControlMessage {
  utc: string;           // ISO timestamp
  lap: number | null;
  category: RaceControlCategory;
  message: string;
}

export interface RaceControlLog {
  entries: RaceControlMessage[];
  updated_at: number;
}

export interface CircuitInfo {
  id: string;
  name: string;
  country: string;
  lat: number;
  lon: number;
  length_km: number;
  total_laps: number;
  lap_record: string;
  lap_record_driver: string;
  lap_record_year: number;
  timezone: string;
}
