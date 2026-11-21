import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { NativeVideoPlayer } from "@/components/NativeVideoPlayer";
import { Loader2, Play, Trash2, Video as VideoIcon } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

type DemoVideo = {
  id: number;
  title: string;
  thumbnailUrl: string | null;
  duration: number | null;
  fileSize: number | null;
  fileUrl: string;
};

const DEMO_VIDEOS: DemoVideo[] = [
  {
    id: 1,
    title: "Flower Demo MP4",
    thumbnailUrl: null,
    duration: 15,
    fileSize: 1200000,
    fileUrl: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: 2,
    title: "Rabbit Demo MP4",
    thumbnailUrl: null,
    duration: 15,
    fileSize: 1500000,
    fileUrl: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
];

export default function VideoLibrary() {
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [deleteVideoId, setDeleteVideoId] = useState<number | null>(null);

  // Fetch videos
  const { data: videos, isLoading, isError, refetch } = trpc.videos.list.useQuery(
    undefined,
    { retry: false }
  );

  const displayedVideos: DemoVideo[] =
    videos && videos.length > 0 ? (videos as DemoVideo[]) : isError || !videos ? DEMO_VIDEOS : [];

  // Get selected video details
  const { data: videoDetails } = trpc.videos.get.useQuery(
    { videoId: selectedVideo! },
    { enabled: !!selectedVideo && !!videos && videos.length > 0, retry: false }
  );

  const selectedDemoVideo =
    videoDetails || displayedVideos.find((v) => v.id === selectedVideo) || null;

  // Delete mutation
  const deleteMutation = trpc.videos.delete.useMutation({
    onSuccess: () => {
      toast.success("Video deleted successfully");
      refetch();
      setDeleteVideoId(null);
    },
    onError: (error) => {
      toast.error(`Failed to delete video: ${error.message}`);
    },
  });

  const formatDuration = (seconds: number | null): string => {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatFileSize = (bytes: number | null): string => {
    if (!bytes) return "N/A";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  // Show video player if video is selected
  if (selectedVideo && selectedDemoVideo) {
    return (
      <NativeVideoPlayer
        videoUrl={selectedDemoVideo.fileUrl}
        title={selectedDemoVideo.title}
        onClose={() => setSelectedVideo(null)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground mb-2">
                Tesla Video Player
              </h1>
              <p className="text-muted-foreground">
                Your video library - watch while driving
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm text-muted-foreground">
                  {displayedVideos.length} videos
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8">
        {isLoading && !isError && displayedVideos.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
              <p className="text-muted-foreground">Loading your videos...</p>
            </div>
          </div>
        ) : displayedVideos.length > 0 ? (
          <div className="video-grid">
            {displayedVideos.map((video) => (
              <Card
                key={video.id}
                className="video-card group