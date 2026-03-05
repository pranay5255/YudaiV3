import { Composition, Folder } from 'remotion';
import { YudaiLoginDemo, type YudaiLoginDemoProps } from './YudaiLoginDemo';
import {
  YudaiFounderTwitterIntro,
  type YudaiFounderTwitterIntroProps,
} from './YudaiFounderTwitterIntro';

export const RemotionRoot: React.FC = () => {
  return (
    <Folder name="Product-Demos">
      <Composition
        id="YudaiFounderTwitterIntro18s"
        component={YudaiFounderTwitterIntro}
        durationInFrames={540}
        fps={30}
        width={1080}
        height={1350}
        defaultProps={
          {
            productName: 'YudaiV3',
          } satisfies YudaiFounderTwitterIntroProps
        }
      />
      <Composition
        id="YudaiLoginDemo15s"
        component={YudaiLoginDemo}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={
          {
            productName: 'YudaiV3',
          } satisfies YudaiLoginDemoProps
        }
      />
    </Folder>
  );
};
