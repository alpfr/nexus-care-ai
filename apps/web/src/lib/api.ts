/**
 * Thin typed wrapper around fetch().
 *
 * All API calls go through here. Centralizing them gives us:
 *   - One place to attach the Authorization header
 *   - One place to translate non-2xx responses into typed errors
 *   - A single base URL that respects the rewrite proxy in next.config.ts
 *
 * Because next.config.ts proxies /api/* to the FastAPI backend, browser
 * fetches use the same origin as the page. No CORS, no preflights.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly raw?: unknown,
  ) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, signal, query } = opts;

  let url = path;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) {
        params.append(k, String(v));
      }
    }
    const qs = params.toString();
    if (qs) url = `${path}?${qs}`;
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
    credentials: "same-origin",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      isJson && typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : typeof payload === "string"
          ? payload
          : "Request failed";
    throw new ApiError(response.status, detail, payload);
  }

  return payload as T;
}

// ---------------------------------------------------------------------------
// Auth + plumbing types (unchanged from tranche 4)
// ---------------------------------------------------------------------------
export interface LoginRequest {
  facility_code: string;
  pin: string;
}
export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}
export interface MeResponse {
  id: number;
  full_name: string;
  role: string;
  tenant_id: number;
  tenant_state: string;
}
export interface HealthResponse {
  status: string;
  database: string;
}
export interface RequestActivationResponse {
  tenant_id: number;
  state: string;
  activation_requested_at: string | null;
  message: string;
}

// ---------------------------------------------------------------------------
// Clinical types (tranche 6a)
// ---------------------------------------------------------------------------
export type ResidentStatus = "admitted" | "discharged" | "deceased";
export type CodeStatus = "full" | "dnr" | "dni" | "dnr_dni" | "comfort_only" | "unknown";
export type FallRisk = "low" | "moderate" | "high" | "unassessed";

export interface ResidentSummary {
  id: number;
  legal_first_name: string;
  legal_last_name: string;
  preferred_name: string | null;
  display_name: string;
  date_of_birth: string;     // ISO date
  admission_date: string;     // ISO date
  status: ResidentStatus;
  room: string | null;
  bed: string | null;
  code_status: CodeStatus;
  fall_risk: FallRisk;
}

export interface ResidentDetail extends ResidentSummary {
  gender: string | null;
  discharge_date: string | null;
  allergies_summary: string | null;
  dietary_restrictions: string | null;
  primary_physician_name: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
  chart_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateResidentRequest {
  legal_first_name: string;
  legal_last_name: string;
  preferred_name?: string | null;
  date_of_birth: string;
  gender?: string | null;
  admission_date: string;
  room?: string | null;
  bed?: string | null;
  allergies_summary?: string | null;
  code_status?: CodeStatus;
  fall_risk?: FallRisk;
  dietary_restrictions?: string | null;
  primary_physician_name?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_relationship?: string | null;
  emergency_contact_phone?: string | null;
  chart_note?: string | null;
}

export type UpdateResidentRequest = Partial<
  Omit<
    CreateResidentRequest,
    "legal_first_name" | "legal_last_name" | "date_of_birth" | "admission_date"
  >
>;

export interface DischargeRequest {
  discharge_date: string;
  reason?: string | null;
  deceased?: boolean;
}

export type DEASchedule = "none" | "II" | "III" | "IV" | "V";
export type MedForm =
  | "tablet" | "capsule" | "liquid" | "oral_solution" | "suspension"
  | "patch" | "cream" | "ointment" | "inhaler" | "nebulizer_solution"
  | "injection" | "suppository" | "eye_drop" | "ear_drop" | "other";

export interface MedicationOut {
  id: number;
  name: string;
  brand_name: string | null;
  strength: string;
  form: MedForm;
  schedule: DEASchedule;
  is_active: boolean;
  is_controlled: boolean;
  notes: string | null;
  display_name: string;
}

export interface CreateMedicationRequest {
  name: string;
  brand_name?: string | null;
  strength: string;
  form: MedForm;
  schedule?: DEASchedule;
  notes?: string | null;
}

export interface UpdateMedicationRequest {
  brand_name?: string | null;
  is_active?: boolean;
  notes?: string | null;
  schedule?: DEASchedule;
}

export type OrderStatus = "pending" | "active" | "held" | "discontinued";
export type RouteOfAdministration =
  | "oral" | "sublingual" | "topical" | "transdermal" | "inhaled"
  | "nebulized" | "subcutaneous" | "intramuscular" | "intravenous"
  | "rectal" | "ophthalmic" | "otic" | "nasal" | "other";

export interface MedicationOrderOut {
  id: number;
  resident_id: number;
  medication_id: number;
  medication_display_name: string;
  medication_schedule: string;
  dose: string;
  route: RouteOfAdministration;
  frequency: string;
  is_prn: boolean;
  prn_indication: string | null;
  prn_max_doses_per_24h: number | null;
  indication: string;
  instructions: string | null;
  prescriber_name: string;
  start_date: string;
  end_date: string | null;
  status: OrderStatus;
  status_reason: string | null;
  witness_required: boolean;
  discontinued_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMedicationOrderRequest {
  medication_id: number;
  dose: string;
  route: RouteOfAdministration;
  frequency: string;
  is_prn?: boolean;
  prn_indication?: string | null;
  prn_max_doses_per_24h?: number | null;
  indication: string;
  instructions?: string | null;
  prescriber_name: string;
  start_date: string;
  end_date?: string | null;
  activate_immediately?: boolean;
}

export interface TransitionOrderRequest {
  target_status: OrderStatus;
  reason?: string | null;
}

export interface UpdateMedicationOrderRequest {
  instructions?: string | null;
  end_date?: string | null;
}

// ---------------------------------------------------------------------------
// API namespace
// ---------------------------------------------------------------------------
export const api = {
  // Health + auth
  health: (signal?: AbortSignal) =>
    request<HealthResponse>("/api/health", { signal }),
  login: (payload: LoginRequest, signal?: AbortSignal) =>
    request<LoginResponse>("/api/login", { method: "POST", body: payload, signal }),
  me: (token: string, signal?: AbortSignal) =>
    request<MeResponse>("/api/me", { token, signal }),
  requestActivation: (token: string, signal?: AbortSignal) =>
    request<RequestActivationResponse>("/api/me/tenant/request-activation", {
      method: "POST",
      token,
      signal,
    }),

  // Residents
  listResidents: (
    token: string,
    include: "active" | "all" | "discharged" = "active",
    signal?: AbortSignal,
  ) =>
    request<ResidentSummary[]>("/api/residents", {
      token,
      query: { include },
      signal,
    }),
  getResident: (token: string, id: number, signal?: AbortSignal) =>
    request<ResidentDetail>(`/api/residents/${id}`, { token, signal }),
  admitResident: (token: string, payload: CreateResidentRequest) =>
    request<ResidentDetail>("/api/residents", {
      method: "POST",
      token,
      body: payload,
    }),
  updateResident: (token: string, id: number, payload: UpdateResidentRequest) =>
    request<ResidentDetail>(`/api/residents/${id}`, {
      method: "PATCH",
      token,
      body: payload,
    }),
  dischargeResident: (token: string, id: number, payload: DischargeRequest) =>
    request<ResidentDetail>(`/api/residents/${id}/discharge`, {
      method: "POST",
      token,
      body: payload,
    }),

  // Medications
  listMedications: (
    token: string,
    opts: { include?: "active" | "all" | "inactive"; q?: string } = {},
    signal?: AbortSignal,
  ) =>
    request<MedicationOut[]>("/api/medications", {
      token,
      query: { include: opts.include ?? "active", q: opts.q },
      signal,
    }),
  getMedication: (token: string, id: number, signal?: AbortSignal) =>
    request<MedicationOut>(`/api/medications/${id}`, { token, signal }),
  createMedication: (token: string, payload: CreateMedicationRequest) =>
    request<MedicationOut>("/api/medications", {
      method: "POST",
      token,
      body: payload,
    }),
  updateMedication: (token: string, id: number, payload: UpdateMedicationRequest) =>
    request<MedicationOut>(`/api/medications/${id}`, {
      method: "PATCH",
      token,
      body: payload,
    }),

  // Medication orders
  listOrdersForResident: (
    token: string,
    residentId: number,
    include: "active" | "all" | "pending" | "held" | "discontinued" = "active",
    signal?: AbortSignal,
  ) =>
    request<MedicationOrderOut[]>(
      `/api/residents/${residentId}/medication-orders`,
      { token, query: { include }, signal },
    ),
  createOrder: (
    token: string,
    residentId: number,
    payload: CreateMedicationOrderRequest,
  ) =>
    request<MedicationOrderOut>(
      `/api/residents/${residentId}/medication-orders`,
      { method: "POST", token, body: payload },
    ),
  getOrder: (token: string, orderId: number, signal?: AbortSignal) =>
    request<MedicationOrderOut>(`/api/medication-orders/${orderId}`, {
      token,
      signal,
    }),
  updateOrder: (
    token: string,
    orderId: number,
    payload: UpdateMedicationOrderRequest,
  ) =>
    request<MedicationOrderOut>(`/api/medication-orders/${orderId}`, {
      method: "PATCH",
      token,
      body: payload,
    }),
  transitionOrder: (
    token: string,
    orderId: number,
    payload: TransitionOrderRequest,
  ) =>
    request<MedicationOrderOut>(`/api/medication-orders/${orderId}/transition`, {
      method: "POST",
      token,
      body: payload,
    }),
};
