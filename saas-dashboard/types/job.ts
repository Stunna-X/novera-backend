export interface Job {
  id: string;
  status: string;
  score: number;
  data: {
    title: string;
  };
}