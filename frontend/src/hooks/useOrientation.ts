import { useState, useEffect } from 'react';

type Orientation = 'portrait' | 'landscape';

export function useOrientation(): Orientation {
  const getOrientation = (): Orientation =>
    window.matchMedia('(orientation: portrait)').matches ? 'portrait' : 'landscape';

  const [orientation, setOrientation] = useState<Orientation>(getOrientation);

  useEffect(() => {
    const mq = window.matchMedia('(orientation: portrait)');
    const handler = () => setOrientation(getOrientation());
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return orientation;
}
