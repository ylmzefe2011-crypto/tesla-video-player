import { z } from "zod";
import { desc, eq } from "drizzle-orm";
import { videos } from "../drizzle/schema";
import { publicProcedure, router } from "./trpc";

const videoIdSchema = z.object({
  videoId: z.number().int().positive(),
});

export const appRouter = router({
  auth: router({
    me: publicProcedure.query(() => {
      return { user: null };
    }),
  }),

  videos: router({
    list: publicProcedure.query(async ({ ctx }) => {
      return await ctx.db
        .select()
        .from(videos)
        .orderBy(desc(videos.createdAt));
    }),

    get: publicProcedure.input(videoIdSchema).query(async ({ ctx, input }) => {
      const rows = await ctx.db
        .select()
        .from(videos)
        .where(eq(videos.id, input.videoId))
        .limit(1);

      return rows[0] ?? null;
    }),

    delete: publicProcedure
      .input(videoIdSchema)
      .mutation(async ({ ctx, input }) => {
        const deleted = await ctx.db
          .delete(videos)
          .where(eq(videos.id, input.videoId))
          .returning({ id: videos.id });

        return { deletedId: deleted[0]?.id ?? null };
      }),
  }),
});

export type AppRouter = typeof appRouter;
