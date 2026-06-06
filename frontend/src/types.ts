export interface Channel {
  id?: string;
  title?: string;
  subscriber_count?: number;
  video_count?: number;
}

export interface RecentVideo {
  id?: string;
  title?: string;
  channel_title?: string;
  published_at?: string;
  view_count?: number;
}

export interface IdeaCard {
  id?: string;
  title?: string;
  score?: number;
  source?: string;
}

export interface DashboardJob {
  id?: string;
  status?: string;
  kind?: string;
}

export interface DashboardData {
  channels: Channel[];
  recent_videos: RecentVideo[];
  idea_cards: IdeaCard[];
  jobs: DashboardJob[];
  comment_collector_status: string;
}
