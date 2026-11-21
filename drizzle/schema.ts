import {
  pgTable,
  serial,
  text,
  integer,
  timestamp,
  boolean,
} from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  telegramId: text("telegram_id").notNull().unique(),
  username: text("username"),
  firstName: text("first_name"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const telegramSessions = pgTable("telegram_sessions", {
  id: serial("id").primaryKey(),
  authToken: text("auth_token").notNull().unique(),
  userId: integer("user_id").references(() => users.id, { onDelete: "cascade" }),
  isAuthenticated: boolean("is_authenticated").default(false).notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  expiresAt: timestamp("expires_at"),
});

export const videos = pgTable("videos", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").references(() => users.id, { onDelete: "cascade" }),
  youtubeId: text("youtube_id"),
  title: text("title").notNull(),
  thumbnailUrl: text("thumbnail_url"),
  duration: integer("duration"),
  fileSize: integer("file_size"),
  fileUrl: text("file_url").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const downloadQueue = pgTable("download_queue", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").references(() => users.id, { onDelete: "cascade" }),
  telegramChatId: text("telegram_chat_id").notNull(),
  youtubeUrl: text("youtube_url").notNull(),
  status: text("status").default("pending").notNull(), // pending | downloading | completed | failed
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});
