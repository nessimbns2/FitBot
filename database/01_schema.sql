-- FitBot PostgreSQL schema (generated from the Alembic migrations)
-- Normally created by: cd backend && alembic upgrade head

CREATE TYPE public.activitylevel AS ENUM (
    'sedentary',
    'light',
    'moderate',
    'very_active',
    'extreme'
);

CREATE TYPE public.experiencelevel AS ENUM (
    'beginner',
    'intermediate',
    'advanced'
);

CREATE TYPE public.goal AS ENUM (
    'hypertrophy',
    'fat_loss',
    'strength',
    'athletic_performance'
);

CREATE TYPE public.logsource AS ENUM (
    'manual',
    'photo_scan',
    'ai_text',
    'ai_suggestion'
);

CREATE TYPE public.mealslotname AS ENUM (
    'breakfast',
    'lunch',
    'dinner',
    'post_workout',
    'snack'
);

CREATE TYPE public.sex AS ENUM (
    'male',
    'female'
);

CREATE TYPE public.somatotype AS ENUM (
    'ectomorph',
    'mesomorph',
    'endomorph',
    'unknown'
);

CREATE TYPE public.unitsystem AS ENUM (
    'metric',
    'imperial'
);

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);

CREATE TABLE public.chat_message (
    id integer NOT NULL,
    session_id character varying(36) NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    sources text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_message_role CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying])::text[])))
);

CREATE SEQUENCE public.chat_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.chat_message_id_seq OWNED BY public.chat_message.id;

CREATE TABLE public.chat_session (
    id character varying(36) NOT NULL,
    user_id integer NOT NULL,
    title character varying(200) DEFAULT 'New conversation'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.deload_records (
    id integer NOT NULL,
    user_id integer NOT NULL,
    exercise_id character varying NOT NULL,
    strategy character varying NOT NULL,
    root_cause character varying NOT NULL,
    confidence character varying NOT NULL,
    target_weight_kg double precision NOT NULL,
    target_sets integer NOT NULL,
    target_reps_range character varying NOT NULL,
    target_rpe_ceiling double precision NOT NULL,
    resume_weight_kg double precision NOT NULL,
    duration_sessions integer NOT NULL,
    constants_version character varying NOT NULL,
    unit character varying NOT NULL,
    plate_increment_kg double precision NOT NULL,
    weight_match_tolerance_kg double precision NOT NULL,
    profile_is_default boolean NOT NULL,
    applied_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    cancel_reason character varying,
    completed_at timestamp with time zone,
    feedback character varying
);

CREATE SEQUENCE public.deload_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.deload_records_id_seq OWNED BY public.deload_records.id;

CREATE TABLE public.food_log_entries (
    id integer NOT NULL,
    user_id integer NOT NULL,
    log_date date NOT NULL,
    meal_slot public.mealslotname NOT NULL,
    name character varying NOT NULL,
    calories double precision NOT NULL,
    protein_g double precision NOT NULL,
    carbs_g double precision NOT NULL,
    fat_g double precision NOT NULL,
    source public.logsource NOT NULL,
    notes character varying,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.food_log_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.food_log_entries_id_seq OWNED BY public.food_log_entries.id;

CREATE TABLE public.meal_logs (
    id integer NOT NULL,
    user_id integer NOT NULL,
    logged_on date DEFAULT CURRENT_DATE NOT NULL,
    slot character varying(40) DEFAULT 'Snack'::character varying NOT NULL,
    meal_name character varying(200) NOT NULL,
    calories integer DEFAULT 0 NOT NULL,
    protein_g double precision DEFAULT '0'::double precision NOT NULL,
    carbs_g double precision DEFAULT '0'::double precision NOT NULL,
    fat_g double precision DEFAULT '0'::double precision NOT NULL,
    food_items json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_meal_logs_calories CHECK ((calories >= 0))
);

CREATE SEQUENCE public.meal_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.meal_logs_id_seq OWNED BY public.meal_logs.id;

CREATE TABLE public.saved_routines (
    id integer NOT NULL,
    user_id integer NOT NULL,
    split character varying(40) DEFAULT 'push_pull_legs'::character varying NOT NULL,
    days_per_week integer DEFAULT 4 NOT NULL,
    routine json NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_saved_routines_days CHECK (((days_per_week >= 1) AND (days_per_week <= 7)))
);

CREATE SEQUENCE public.saved_routines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.saved_routines_id_seq OWNED BY public.saved_routines.id;

CREATE TABLE public.user_profile (
    id integer NOT NULL,
    user_id integer NOT NULL,
    age integer DEFAULT 25 NOT NULL,
    sex public.sex DEFAULT 'male'::public.sex NOT NULL,
    height_cm double precision DEFAULT '175'::double precision NOT NULL,
    weight_kg double precision DEFAULT '75'::double precision NOT NULL,
    body_fat_pct double precision,
    experience_level public.experiencelevel DEFAULT 'beginner'::public.experiencelevel NOT NULL,
    somatotype public.somatotype DEFAULT 'unknown'::public.somatotype NOT NULL,
    goal public.goal DEFAULT 'hypertrophy'::public.goal NOT NULL,
    activity_level public.activitylevel DEFAULT 'moderate'::public.activitylevel NOT NULL,
    unit_system public.unitsystem DEFAULT 'metric'::public.unitsystem NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_profile_age CHECK (((age >= 14) AND (age <= 100))),
    CONSTRAINT ck_profile_body_fat CHECK (((body_fat_pct IS NULL) OR ((body_fat_pct >= (3)::double precision) AND (body_fat_pct <= (60)::double precision)))),
    CONSTRAINT ck_profile_height CHECK (((height_cm >= (120)::double precision) AND (height_cm <= (230)::double precision))),
    CONSTRAINT ck_profile_weight CHECK (((weight_kg >= (30)::double precision) AND (weight_kg <= (300)::double precision)))
);

CREATE SEQUENCE public.user_profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.user_profile_id_seq OWNED BY public.user_profile.id;

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(120) NOT NULL,
    password_hash character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone
);

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

CREATE TABLE public.workout_sets (
    id integer NOT NULL,
    user_id integer NOT NULL,
    exercise_id character varying(100) NOT NULL,
    performed_at timestamp with time zone DEFAULT now() NOT NULL,
    session_label character varying(100),
    set_number integer DEFAULT 1 NOT NULL,
    reps integer NOT NULL,
    weight_kg double precision NOT NULL,
    rpe double precision,
    rir integer,
    notes text,
    CONSTRAINT ck_workout_sets_reps CHECK (((reps >= 1) AND (reps <= 100))),
    CONSTRAINT ck_workout_sets_weight CHECK (((weight_kg >= (0)::double precision) AND (weight_kg <= (500)::double precision)))
);

CREATE SEQUENCE public.workout_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.workout_sets_id_seq OWNED BY public.workout_sets.id;

ALTER TABLE ONLY public.chat_message ALTER COLUMN id SET DEFAULT nextval('public.chat_message_id_seq'::regclass);

ALTER TABLE ONLY public.deload_records ALTER COLUMN id SET DEFAULT nextval('public.deload_records_id_seq'::regclass);

ALTER TABLE ONLY public.food_log_entries ALTER COLUMN id SET DEFAULT nextval('public.food_log_entries_id_seq'::regclass);

ALTER TABLE ONLY public.meal_logs ALTER COLUMN id SET DEFAULT nextval('public.meal_logs_id_seq'::regclass);

ALTER TABLE ONLY public.saved_routines ALTER COLUMN id SET DEFAULT nextval('public.saved_routines_id_seq'::regclass);

ALTER TABLE ONLY public.user_profile ALTER COLUMN id SET DEFAULT nextval('public.user_profile_id_seq'::regclass);

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

ALTER TABLE ONLY public.workout_sets ALTER COLUMN id SET DEFAULT nextval('public.workout_sets_id_seq'::regclass);

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT chat_session_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.deload_records
    ADD CONSTRAINT deload_records_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.food_log_entries
    ADD CONSTRAINT food_log_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.meal_logs
    ADD CONSTRAINT meal_logs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.saved_routines
    ADD CONSTRAINT saved_routines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.workout_sets
    ADD CONSTRAINT workout_sets_pkey PRIMARY KEY (id);

CREATE INDEX ix_chat_message_session_id ON public.chat_message USING btree (session_id);

CREATE INDEX ix_chat_session_user_id ON public.chat_session USING btree (user_id);

CREATE INDEX ix_deload_records_applied_at ON public.deload_records USING btree (applied_at);

CREATE INDEX ix_deload_records_exercise_id ON public.deload_records USING btree (exercise_id);

CREATE INDEX ix_deload_records_user_id ON public.deload_records USING btree (user_id);

CREATE INDEX ix_food_log_entries_log_date ON public.food_log_entries USING btree (log_date);

CREATE INDEX ix_food_log_entries_user_id ON public.food_log_entries USING btree (user_id);

CREATE INDEX ix_meal_logs_logged_on ON public.meal_logs USING btree (logged_on);

CREATE INDEX ix_meal_logs_user_id ON public.meal_logs USING btree (user_id);

CREATE UNIQUE INDEX ix_saved_routines_user_id ON public.saved_routines USING btree (user_id);

CREATE UNIQUE INDEX ix_user_profile_user_id ON public.user_profile USING btree (user_id);

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);

CREATE INDEX ix_workout_sets_exercise_id ON public.workout_sets USING btree (exercise_id);

CREATE INDEX ix_workout_sets_performed_at ON public.workout_sets USING btree (performed_at);

CREATE INDEX ix_workout_sets_user_id ON public.workout_sets USING btree (user_id);

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_session(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT chat_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.deload_records
    ADD CONSTRAINT deload_records_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.food_log_entries
    ADD CONSTRAINT food_log_entries_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.meal_logs
    ADD CONSTRAINT meal_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.saved_routines
    ADD CONSTRAINT saved_routines_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.workout_sets
    ADD CONSTRAINT workout_sets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
