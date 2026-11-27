import { useThemeStore } from '../store/themeStore';

interface BrandLogoProps {
  variant?: 'horizontal' | 'mark';
  surface?: 'auto' | 'light' | 'dark';
  height?: number;
}

export function BrandLogo({
  variant = 'horizontal',
  surface = 'auto',
  height = 24,
}: BrandLogoProps) {
  const theme = useThemeStore((s) => s.theme);

  if (variant === 'mark') {
    return (
      <img
        src="/static/brand/mark-coral.png"
        alt="AcquireMock"
        height={height}
        width={height}
        style={{ height, width: height, objectFit: 'contain' }}
      />
    );
  }

  const useDarkLogo = surface === 'dark' || (surface === 'auto' && theme === 'dark');
  const src = useDarkLogo
    ? '/static/brand/logo-horizontal-dark.png'
    : '/static/brand/logo-horizontal-light.png';

  return (
    <img
      src={src}
      alt="AcquireMock"
      height={height}
      style={{ height, width: 'auto', objectFit: 'contain' }}
    />
  );
}
