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

export type YudaiLoginDemoProps = {
  productName: string;
};

const fontFamily = 'Inter, Segoe UI, Arial, sans-serif';

const heroBullets = [
  'File dependency mapping',
  'Chat summaries',
  'Review-ready PRs',
];

const workflow = [
  {
    step: '01',
    title: 'Connect',
    description:
      'Link your GitHub repository and map dependencies automatically.',
  },
  {
    step: '02',
    title: 'Converse',
    description:
      'Capture context cards from each conversation about your codebase.',
  },
  {
    step: '03',
    title: 'Generate',
    description: 'Produce small, focused pull requests ready for review.',
  },
  {
    step: '04',
    title: 'Audit',
    description: 'Track full trajectories for every decision and code change.',
  },
];

const capabilities = [
  'GitHub-native AI coding workspace',
  'Persistent repo-scoped chat sessions',
  'Context cards and issue drafting',
  'Solver workflows with trajectory streaming',
];

const appear = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

const slideUpStyle = (
  frame: number,
  start: number,
  duration: number,
  distance = 30,
): React.CSSProperties => {
  const progress = appear(frame, start, duration);
  return {
    opacity: progress,
    transform: `translateY(${(1 - progress) * distance}px)`,
  };
};

const HeroScene: React.FC<YudaiLoginDemoProps> = ({ productName }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const popIn = spring({
    fps,
    frame,
    config: {
      damping: 18,
      stiffness: 130,
      mass: 0.7,
    },
  });

  return (
    <AbsoluteFill style={{ justifyContent: 'center', padding: '120px 160px' }}>
      <div style={{ ...slideUpStyle(frame, 0, 20), color: '#7dd3fc', fontFamily, fontSize: 28, letterSpacing: 4 }}>
        CONTEXT-ENGINEERED AGENT
      </div>
      <div
        style={{
          marginTop: 24,
          color: '#f8fafc',
          fontFamily,
          fontWeight: 700,
          fontSize: 86,
          lineHeight: 1.05,
          transform: `scale(${0.96 + popIn * 0.04})`,
          opacity: interpolate(frame, [0, 18], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
        }}
      >
        {productName}
        <br />
        Chat summaries, file insights,
        <br />
        review-ready PRs.
      </div>
      <div style={{ ...slideUpStyle(frame, 16, 18), marginTop: 28, maxWidth: 1240, color: '#cbd5e1', fontFamily, fontSize: 36, lineHeight: 1.35 }}>
        Connect your GitHub repository and turn curated context into small,
        focused pull requests with auditable trajectories.
      </div>
      <div style={{ display: 'flex', gap: 18, marginTop: 34 }}>
        {heroBullets.map((item, index) => (
          <div
            key={item}
            style={{
              ...slideUpStyle(frame, 26 + index * 8, 14, 18),
              border: '1px solid rgba(125, 211, 252, 0.45)',
              borderRadius: 999,
              padding: '10px 20px',
              color: '#bae6fd',
              fontFamily,
              fontSize: 24,
            }}
          >
            {item}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const WorkflowScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ padding: '110px 150px', fontFamily }}>
      <div style={{ ...slideUpStyle(frame, 0, 16), color: '#f8fafc', fontSize: 62, fontWeight: 700 }}>
        How it works
      </div>
      <div style={{ ...slideUpStyle(frame, 6, 16), marginTop: 16, color: '#cbd5e1', fontSize: 30, maxWidth: 1100 }}>
        Login page flow from your UI: Connect, Converse, Generate, Audit.
      </div>

      <div
        style={{
          marginTop: 48,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 24,
        }}
      >
        {workflow.map((item, index) => (
          <div
            key={item.step}
            style={{
              ...slideUpStyle(frame, 14 + index * 10, 14, 24),
              border: '1px solid rgba(148, 163, 184, 0.28)',
              borderRadius: 20,
              padding: 28,
              background: 'rgba(15, 23, 42, 0.58)',
            }}
          >
            <div style={{ color: '#fbbf24', fontSize: 22, letterSpacing: 2, fontWeight: 600 }}>
              {item.step}
            </div>
            <div style={{ marginTop: 8, color: '#f8fafc', fontSize: 36, fontWeight: 700 }}>
              {item.title}
            </div>
            <div style={{ marginTop: 10, color: '#cbd5e1', fontSize: 24, lineHeight: 1.35 }}>
              {item.description}
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const CapabilityScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ padding: '120px 150px', fontFamily }}>
      <div style={{ ...slideUpStyle(frame, 0, 16), color: '#f8fafc', fontSize: 58, fontWeight: 700 }}>
        Built for real coding workflows
      </div>
      <div style={{ ...slideUpStyle(frame, 8, 16), marginTop: 14, color: '#cbd5e1', fontSize: 30 }}>
        Highlights from your README and current product scope
      </div>

      <div style={{ marginTop: 44, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {capabilities.map((item, index) => (
          <div
            key={item}
            style={{
              ...slideUpStyle(frame, 16 + index * 8, 14, 20),
              borderRadius: 18,
              padding: 22,
              border: '1px solid rgba(56, 189, 248, 0.35)',
              background:
                'linear-gradient(135deg, rgba(14, 116, 144, 0.18) 0%, rgba(2, 6, 23, 0.36) 100%)',
              color: '#e2e8f0',
              fontSize: 28,
              lineHeight: 1.3,
            }}
          >
            {item}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const OnboardingScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ justifyContent: 'center', padding: '120px 170px', fontFamily }}>
      <div style={{ ...slideUpStyle(frame, 0, 14), color: '#f8fafc', fontSize: 68, fontWeight: 700 }}>
        2-step onboarding
      </div>
      <div style={{ ...slideUpStyle(frame, 8, 14), marginTop: 14, color: '#cbd5e1', fontSize: 34 }}>
        Sign in with GitHub, then install the app for repository access.
      </div>
      <div style={{ display: 'flex', gap: 18, marginTop: 30 }}>
        {['1. Sign in with GitHub', '2. Install GitHub App'].map(
          (item, index) => (
            <div
              key={item}
              style={{
                ...slideUpStyle(frame, 14 + index * 8, 14, 20),
                borderRadius: 14,
                border: '1px solid rgba(251, 191, 36, 0.4)',
                background: 'rgba(15, 23, 42, 0.58)',
                color: '#fde68a',
                fontSize: 30,
                fontWeight: 600,
                padding: '16px 24px',
              }}
            >
              {item}
            </div>
          ),
        )}
      </div>
      <div style={{ ...slideUpStyle(frame, 22, 14), marginTop: 34, color: '#7dd3fc', fontSize: 42, fontWeight: 600 }}>
        Join Discord: discord.gg/U96mwKmJ
      </div>
    </AbsoluteFill>
  );
};

export const YudaiLoginDemo: React.FC<YudaiLoginDemoProps> = (props) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const glowX = interpolate(frame, [0, 450], [width * 0.25, width * 0.8], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const glowY = interpolate(frame, [0, 450], [height * 0.2, height * 0.65], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background:
          'linear-gradient(140deg, #020617 0%, #0f172a 42%, #111827 100%)',
        overflow: 'hidden',
      }}
    >
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 18% 12%, rgba(245, 158, 11, 0.22), transparent 35%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: glowX - 220,
          top: glowY - 220,
          width: 440,
          height: 440,
          borderRadius: 220,
          filter: 'blur(80px)',
          background: 'rgba(56, 189, 248, 0.2)',
        }}
      />

      <Sequence from={0} durationInFrames={120} premountFor={30}>
        <HeroScene {...props} />
      </Sequence>

      <Sequence from={120} durationInFrames={140} premountFor={30}>
        <WorkflowScene />
      </Sequence>

      <Sequence from={260} durationInFrames={100} premountFor={30}>
        <CapabilityScene />
      </Sequence>

      <Sequence from={360} durationInFrames={90} premountFor={30}>
        <OnboardingScene />
      </Sequence>
    </AbsoluteFill>
  );
};
