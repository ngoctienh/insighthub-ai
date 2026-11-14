export type RoleCode =
  | "ADMIN"
  | "PRODUCT_MANAGER"
  | "DEVELOPER"
  | "CUSTOMER_SUPPORT"
  | "CUSTOMER";

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  display_name: string;
  role_code: RoleCode;
  role_name: string;
  job_title: string;
  department: string;
  avatar_url: string;
  is_active: boolean;
  permissions?: string[];
  email_notifications_enabled?: boolean;
  date_joined?: string;
  last_login?: string | null;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  description: string;
  category: string;
  owner: number | null;
  is_active: boolean;
  feedback_count?: number;
}

export interface FeedbackSource {
  id: number;
  code: "WEB_FORM" | "EMAIL" | "LIVE_CHAT" | "COMMUNITY";
  name: string;
  channel_type: string;
  description: string;
  webhook_token?: string;
  is_active: boolean;
  feedback_count?: number;
}

export interface Tag {
  id: number;
  name: string;
  slug: string;
  color: string;
  description: string;
}

export interface InsightBrief {
  id: number;
  code: string;
  title: string;
  priority_score: number;
  priority_level: PriorityLevel;
  status: InsightStatus;
}

export type FeedbackStatus =
  | "NEW"
  | "TRIAGING"
  | "ANALYZING"
  | "PLANNED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CLOSED"
  | "DUPLICATE";

export type ImpactLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type PriorityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type InsightStatus = "NEW" | "ANALYZING" | "PLANNED" | "IN_PROGRESS" | "COMPLETED";
export type VerificationStatus = "PENDING_REVIEW" | "CONFIRMED" | "REJECTED";
export type RoadmapStatus = "PLANNED" | "IN_PROGRESS" | "COMPLETED";
export type RoadmapVisibility = "PUBLIC" | "PRIVATE";

export interface Feedback {
  id: number;
  code: string;
  title: string;
  content: string;
  normalized_content?: string;
  embedding_model?: string;
  sender_name: string;
  sender_email: string;
  author: number | null;
  product: number;
  product_name: string;
  source: number;
  source_code: "WEB_FORM" | "EMAIL" | "LIVE_CHAT" | "COMMUNITY";
  source_name: string;
  external_reference_id?: string;
  source_metadata?: Record<string, unknown>;
  status: FeedbackStatus;
  impact_level: ImpactLevel;
  priority_score: number | null;
  assigned_to: number | null;
  assigned_to_detail: User | null;
  duplicate_of: number | null;
  duplicate_of_detail?: { id: number; code: string; title: string; status: string } | null;
  similarity_score: number | null;
  is_duplicate_confirmed: boolean;
  tags: Tag[];
  related_insights: InsightBrief[];
  votes_count: number;
  user_has_voted: boolean;
  comments_count: number;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

export interface InsightMember {
  id: number;
  feedback_id: number;
  code: string;
  title: string;
  content: string;
  sender_name: string;
  sender_email: string;
  source_code: string;
  impact_level: ImpactLevel;
  status: FeedbackStatus;
  similarity_to_centroid: number | null;
  added_by_ai: boolean;
  submitted_at: string;
}

export interface InsightGroup {
  id: number;
  code: string;
  product: number;
  product_name: string;
  title: string;
  description: string;
  possible_causes?: string[];
  user_impact?: string;
  ai_recommendations?: string[];
  draft_customer_reply?: string;
  analysis_mode: string;
  ai_confidence: number;
  volume_score: number;
  impact_score: number;
  severity_score: number;
  priority_score: number;
  priority_level: PriorityLevel;
  priority_reasoning?: string;
  is_priority_overridden: boolean;
  pm_priority_notes?: string;
  status: InsightStatus;
  verification_status: VerificationStatus;
  feedback_count: number;
  affected_customers_count: number;
  assigned_to: number | null;
  assigned_to_detail: User | null;
  due_date: string | null;
  votes_count: number;
  user_has_voted: boolean;
  members?: InsightMember[];
  roadmap_items?: {
    id: number;
    code: string;
    title: string;
    status: RoadmapStatus;
    visibility: RoadmapVisibility;
    quarter: string;
    progress_percent: number;
  }[];
  created_at: string;
  updated_at: string;
}

export interface RoadmapItem {
  id: number;
  code: string;
  product: number;
  product_name: string;
  title: string;
  description: string;
  public_description: string;
  internal_notes: string;
  status: RoadmapStatus;
  visibility: RoadmapVisibility;
  quarter: string;
  target_start_date: string | null;
  target_end_date: string | null;
  progress_percent: number;
  owner: number | null;
  owner_detail: User | null;
  linked_insights: {
    id: number;
    code: string;
    title: string;
    priority_score: number;
    priority_level: PriorityLevel;
    feedback_count: number;
    status: InsightStatus;
  }[];
  created_at: string;
  updated_at: string;
}

export interface PublicRoadmapItem {
  id: number;
  code: string;
  product: number;
  product_name: string;
  title: string;
  summary: string;
  status: RoadmapStatus;
  quarter: string;
  target_start_date: string | null;
  target_end_date: string | null;
  progress_percent: number;
  linked_insights_count: number;
  total_linked_feedbacks: number;
  updated_at: string;
}

export interface CommentItem {
  id: number;
  author: User;
  content: string;
  is_internal: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: number;
  event_type: string;
  title: string;
  message: string;
  actor_name: string;
  feedback: number | null;
  insight_group: number | null;
  roadmap_item: number | null;
  link_url: string;
  is_read: boolean;
  created_at: string;
}

export interface ActivityLogItem {
  id: number;
  actor: User | null;
  entity_type: string;
  entity_id: number;
  action: string;
  old_value: unknown;
  new_value: unknown;
  description: string;
  created_at: string;
}

export interface DuplicateCandidate {
  feedback_a_id: number;
  feedback_a_code: string;
  feedback_a_title: string;
  feedback_b_id: number;
  feedback_b_code: string;
  feedback_b_title: string;
  similarity_score: number;
  is_exact_normalized_match: boolean;
}

export interface AIAnalysisJob {
  id: number;
  product: number | null;
  product_name: string;
  triggered_by_detail: User | null;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  duplicate_candidates: DuplicateCandidate[];
  unassigned_feedback_ids: number[];
  analysis_mode: string;
  error_message: string;
  created_at: string;
  completed_at: string | null;
}

export interface DashboardData {
  kpis: {
    total_feedbacks: number;
    new_feedbacks: number;
    insights_detected: number;
    in_progress_issues: number;
    completed_issues: number;
    duplicate_feedbacks: number;
  };
  feedbacks_by_date: { date: string; count: number }[];
  feedbacks_by_source: { source_code: string; name: string; count: number }[];
  by_priority: { level: PriorityLevel; count: number }[];
  top_5_issues: {
    id: number;
    code: string;
    title: string;
    feedback_count: number;
    affected_customers_count: number;
    priority_score: number;
    priority_level: PriorityLevel;
    status: InsightStatus;
  }[];
  urgent_insights: {
    id: number;
    code: string;
    title: string;
    priority_score: number;
    priority_level: PriorityLevel;
    feedback_count: number;
    affected_customers_count: number;
    status: InsightStatus;
    verification_status: VerificationStatus;
    due_date: string | null;
  }[];
}
