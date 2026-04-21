import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type YudaiFounderTwitterIntroProps = {
  productName: string;
};

const fontHeading = '"Space Grotesk", "Inter", "Segoe UI", sans-serif';
const fontBody = '"DM Sans", "Inter", "Segoe UI", sans-serif';
const totalFrames = 540;

const clamp = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

const fadeInOut = (frame: number, duration: number, fadeFrames = 12) => {
  const fadeIn = interpolate(frame, [0, fadeFrames], [0, 1], clamp);
  const fadeOut = interpolate(
    frame,
    [duration - fadeFrames, duration],
    [1, 0],
    clamp,
  );

  return Math.min(fadeIn, fadeOut);
};

const enterUp = (frame: number, start: number, duration: number, offset = 24) => {
  const progress = interpolate(frame, [start, start + duration], [0, 1], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });

  return {
    opacity: progress,
    transform: `translateY(${(1 - progress) * offset}px)`,
  };
};

const IntroScene: React.FC<YudaiFounderTwitterIntroProps & { duration: number }> = ({
  productName,
  duration,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const hookText = 'Enterprise teams: ship governed product changes with full audit confidence.';
  const typedChars = Math.floor(
    interpolate(frame, [0, Math.floor(2.1 * fps)], [0, hookText.length], clamp),
  );
  const cursorVisible = Math.floor(frame / 10) % 2 === 0;
  const scaleIn = spring({
    fps,
    frame,
    config: { damping: 18, stiffness: 130, mass: 0.7 },
  });
  const headlineMotion = enterUp(frame, 6, 20, 24);

  return (
    <AbsoluteFill
      style={{
        padding: '96px 84px',
        opacity: fadeInOut(frame, duration),
      }}
    >
      <div
        style={{
          ...enterUp(frame, 0, 16, 18),
          fontFamily: fontBody,
          color: '#38bdf8',
          fontWeight: 600,
          letterSpacing: 2,
          fontSize: 28,
          textTransform: 'uppercase',
        }}
      >
        Enterprise intro
      </div>

      <div
        style={{
          marginTop: 22,
          ...headlineMotion,
          fontFamily: fontHeading,
          color: '#f8fafc',
          fontWeight: 700,
          fontSize: 78,
          lineHeight: 1.06,
          transform: `${headlineMotion.transform} scale(${0.97 + scaleIn * 0.03})`,
        }}
      >
        {productName}
        <br />
        Idea to issue,
        <br />
        tests, and PR.
      </div>

      <div
        style={{
          marginTop: 26,
          fontFamily: fontBody,
          color: '#e2e8f0',
          fontSize: 34,
          lineHeight: 1.35,
          minHeight: 96,
          ...enterUp(frame, 16, 18, 20),
        }}
      >
        {hookText.slice(0, typedChars)}
        <span style={{ opacity: cursorVisible ? 1 : 0 }}>|</span>
      </div>

      <div style={{ display: 'flex', gap: 14, marginTop: 26 }}>
        {['Architect writes issue', 'Tester adds tests', 'Coder opens PR'].map(
          (chip, index) => (
            <div
              key={chip}
              style={{
                ...enterUp(frame, 24 + index * 8, 14, 18),
                border: '1px solid rgba(56, 189, 248, 0.45)',
                borderRadius: 999,
                padding: '10px 16px',
                fontFamily: fontBody,
                color: '#bae6fd',
                fontSize: 24,
                background: 'rgba(8, 47, 73, 0.25)',
              }}
            >
              {chip}
            </div>
          ),
        )}
      </div>
    </AbsoluteFill>
  );
};

const ModeScene: React.FC<{ duration: number }> = ({ duration }) => {
  const frame = useCurrentFrame();

  const modeCards = [
    {
      title: 'Architect Mode',
      summary: 'Turns your request into a concrete GitHub issue with acceptance criteria.',
      accent: '#22d3ee',
    },
    {
      title: 'Tester Mode',
      summary: 'Writes unit, integration, and edge-case tests before implementation.',
      accent: '#f59e0b',
    },
    {
      title: 'Coder Mode',
      summary: 'Implements, runs tests, and ships a review-ready pull request.',
      accent: '#34d399',
    },
  ];

  return (
    <AbsoluteFill
      style={{
        padding: '92px 84px',
        opacity: fadeInOut(frame, duration),
      }}
    >
      <div
        style={{
          ...enterUp(frame, 0, 14, 16),
          fontFamily: fontHeading,
          color: '#f8fafc',
          fontSize: 60,
          fontWeight: 700,
          lineHeight: 1.1,
        }}
      >
        One run. Three specialized modes.
      </div>
      <div
        style={{
          ...enterUp(frame, 8, 14, 16),
          marginTop: 12,
          fontFamily: fontBody,
          color: '#cbd5e1',
          fontSize: 30,
          lineHeight: 1.35,
          maxWidth: 820,
        }}
      >
        Planned from your implementation docs: Architect → Tester → Coder.
      </div>

      <div style={{ marginTop: 34, display: 'grid', gap: 18 }}>
        {modeCards.map((card, index) => {
          const start = 14 + index * 12;
          const progress = interpolate(frame, [start + 8, start + 28], [0, 1], clamp);
          return (
            <div
              key={card.title}
              style={{
                ...enterUp(frame, start, 14, 18),
                borderRadius: 18,
                border: '1px solid rgba(148, 163, 184, 0.32)',
                background: 'rgba(15, 23, 42, 0.72)',
                padding: 24,
              }}
            >
              <div
                style={{
                  fontFamily: fontHeading,
                  color: '#f8fafc',
                  fontSize: 36,
                  fontWeight: 600,
                }}
              >
                {card.title}
              </div>
              <div
                style={{
                  marginTop: 8,
                  fontFamily: fontBody,
                  color: '#cbd5e1',
                  fontSize: 26,
                  lineHeight: 1.35,
                }}
              >
                {card.summary}
              </div>
              <div
                style={{
                  marginTop: 14,
                  height: 8,
                  borderRadius: 999,
                  background: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(51, 65, 85, 0.8)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.max(0, Math.min(1, progress)) * 100}%`,
                    background: card.accent,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const RealtimeScene: React.FC<{ duration: number }> = ({ duration }) => {
  const frame = useCurrentFrame();

  const points = [
    'Sandbox identity: org + repo + environment',
    'Realtime split: WebSocket chat + SSE trajectory streaming',
    'Persistence ends only after issue + PR are created',
  ];

  return (
    <AbsoluteFill
      style={{
        padding: '90px 84px',
        opacity: fadeInOut(frame, duration),
      }}
    >
      <div
        style={{
          ...enterUp(frame, 0, 16, 16),
          fontFamily: fontHeading,
          color: '#f8fafc',
          fontSize: 58,
          fontWeight: 700,
          lineHeight: 1.1,
        }}
      >
        Built for real product velocity
      </div>

      <div style={{ marginTop: 28, display: 'grid', gap: 14 }}>
        {points.map((point, index) => (
          <div
            key={point}
            style={{
              ...enterUp(frame, 10 + index * 10, 14, 16),
              borderRadius: 16,
              border: '1px solid rgba(125, 211, 252, 0.38)',
              background:
                'linear-gradient(135deg, rgba(8, 47, 73, 0.3) 0%, rgba(15, 23, 42, 0.76) 100%)',
              padding: '18px 20px',
              fontFamily: fontBody,
              color: '#e2e8f0',
              fontSize: 27,
              lineHeight: 1.3,
            }}
          >
            {point}
          </div>
        ))}
      </div>

      <div
        style={{
          ...enterUp(frame, 34, 14, 18),
          marginTop: 28,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: 14,
        }}
      >
        {[
          { label: 'Target startup', value: '~10s' },
          { label: 'Target stream latency', value: '~1s' },
          { label: 'Tunnel token TTL', value: '1h' },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              borderRadius: 14,
              padding: '14px 12px',
              border: '1px solid rgba(148, 163, 184, 0.3)',
              background: 'rgba(15, 23, 42, 0.7)',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                fontFamily: fontHeading,
                fontSize: 38,
                color: '#f8fafc',
                fontWeight: 700,
                lineHeight: 1.1,
              }}
            >
              {stat.value}
            </div>
            <div
              style={{
                marginTop: 4,
                fontFamily: fontBody,
                fontSize: 19,
                color: '#94a3b8',
              }}
            >
              {stat.label}
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const CTAScene: React.FC<YudaiFounderTwitterIntroProps & { duration: number }> = ({
  productName,
  duration,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pulse = spring({
    fps,
    frame,
    config: { damping: 12, stiffness: 120, mass: 0.8 },
    durationInFrames: 44,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        padding: '84px',
        opacity: fadeInOut(frame, duration),
      }}
    >
      <div
        style={{
          ...enterUp(frame, 0, 16, 16),
          fontFamily: fontHeading,
          color: '#f8fafc',
          fontSize: 74,
          lineHeight: 1.05,
          fontWeight: 700,
        }}
      >
        Ship with control.
        <br />
        Scale with confidence.
      </div>
      <div
        style={{
          ...enterUp(frame, 10, 16, 16),
          marginTop: 16,
          fontFamily: fontBody,
          color: '#cbd5e1',
          fontSize: 33,
          lineHeight: 1.35,
          maxWidth: 820,
        }}
      >
        {productName} is built for engineering organizations shipping high-stakes
        updates every week.
      </div>

      <div
        style={{
          ...enterUp(frame, 18, 16, 16),
          marginTop: 24,
          display: 'inline-flex',
          borderRadius: 999,
          border: '1px solid rgba(251, 191, 36, 0.45)',
          padding: '12px 20px',
          background: 'rgba(146, 64, 14, 0.28)',
          color: '#fde68a',
          fontFamily: fontBody,
          fontSize: 24,
          fontWeight: 600,
        }}
      >
        2-step onboarding: Sign in with GitHub → Install GitHub App
      </div>

      <div
        style={{
          ...enterUp(frame, 28, 16, 16),
          marginTop: 24,
          transform: `scale(${0.98 + pulse * 0.02})`,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 14,
          border: '1px solid rgba(56, 189, 248, 0.55)',
          background: 'rgba(8, 47, 73, 0.5)',
          color: '#e0f2fe',
          fontFamily: fontHeading,
          fontSize: 30,
          fontWeight: 600,
          padding: '14px 22px',
          maxWidth: 580,
        }}
      >
        yudai.app
      </div>
    </AbsoluteFill>
  );
};

export const YudaiFounderTwitterIntro: React.FC<YudaiFounderTwitterIntroProps> = (
  props,
) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const glowX = interpolate(frame, [0, totalFrames], [width * 0.18, width * 0.84], clamp);
  const glowY = interpolate(
    frame,
    [0, totalFrames],
    [height * 0.15, height * 0.76],
    clamp,
  );

  return (
    <AbsoluteFill
      style={{
        background:
          'linear-gradient(140deg, #020617 0%, #0f172a 40%, #111827 100%)',
        overflow: 'hidden',
      }}
    >
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 10% 4%, rgba(245, 158, 11, 0.2), transparent 35%)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: glowX - 210,
          top: glowY - 210,
          width: 420,
          height: 420,
          borderRadius: 999,
          filter: 'blur(86px)',
          background: 'rgba(56, 189, 248, 0.2)',
        }}
      />

      <Sequence from={0} durationInFrames={150}>
        <IntroScene {...props} duration={150} />
      </Sequence>
      <Sequence from={130} durationInFrames={150}>
        <ModeScene duration={150} />
      </Sequence>
      <Sequence from={260} durationInFrames={140}>
        <RealtimeScene duration={140} />
      </Sequence>
      <Sequence from={390} durationInFrames={150}>
        <CTAScene {...props} duration={150} />
      </Sequence>
    </AbsoluteFill>
  );
};
