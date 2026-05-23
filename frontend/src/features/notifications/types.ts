export type Notification = {
  id: string;
  title: string;
  subtitle: string;
  timestamp: string;
  read: boolean;
};

export type NotificationFeed = {
  items: Notification[];
  unreadCount: number;
};
