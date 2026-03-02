import { Composition, Folder } from 'remotion';
import { YudaiLoginDemo, type YudaiLoginDemoProps } from './YudaiLoginDemo';

export const RemotionRoot: React.FC = () => {
  return (
    <Folder name="Product-Demos">
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
