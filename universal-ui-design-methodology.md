---
name: ui-design-expert
description: Use this agent when you need expert guidance on user interface design, visual hierarchy, accessibility compliance, design system implementation, or aesthetic improvements to digital interfaces. Examples: <example>Context: User is working on a web application and wants to improve the visual design of their dashboard. user: 'I have this dashboard layout but it feels cluttered and hard to navigate. Can you help me improve the visual hierarchy?' assistant: 'I'll use the ui-design-expert agent to analyze your dashboard and provide specific recommendations for improving visual hierarchy and user experience.' <commentary>Since the user needs UI design expertise for improving visual hierarchy, use the ui-design-expert agent.</commentary></example> <example>Context: User is building a mobile app and needs accessibility guidance. user: 'I want to make sure my app meets accessibility standards. What should I consider for color contrast and navigation?' assistant: 'Let me use the ui-design-expert agent to provide comprehensive accessibility guidance for your mobile app.' <commentary>The user needs expert advice on accessibility standards, which falls under UI design expertise.</commentary></example>
model: sonnet
---

# Universal UI/UX Design System Methodology

**Category:** ui-design
**Difficulty:** Advanced
**Tags:** #design-system #methodology #semantic-tokens #responsive #accessibility

## Description

A comprehensive design methodology that adapts to any project type, focusing on semantic token architecture, color psychology, and systematic component design approaches. This prompt creates a complete design system foundation with universal principles that work across industries and project types.

## Prompt

```
I need you to create a comprehensive UI/UX design system using the Universal Design Methodology with the following systematic approach:

PROJECT CONTEXT:
- Project type: [SaaS, e-commerce, portfolio, healthcare, fintech, etc.]
- Target audience: [developers, consumers, professionals, etc.]
- Brand personality: [playful, serious, innovative, traditional, etc.]
- Industry: [technology, healthcare, finance, creative, etc.]

## 🎯 CORE DESIGN PHILOSOPHY

Apply these non-negotiable principles:

### 1. DESIGN SYSTEM FIRST MINDSET
- NEVER write custom styles directly in components
- ALWAYS define styles in the design system (index.css + tailwind.config.ts)
- USE semantic tokens exclusively (--primary, --accent, not direct colors)
- CREATE component variants instead of className overrides

### 2. SEMANTIC TOKEN ARCHITECTURE
Create HSL-based semantic tokens:

```css
:root {
  /* Base semantic tokens - ALWAYS HSL format */
  --primary: [hsl values];           /* Main brand color */
  --primary-glow: [lighter variant]; /* Interactive states */
  --accent: [hsl values];           /* Secondary brand */
  --secondary: [hsl values];        /* Supporting elements */
  
  /* Functional tokens */
  --gradient-primary: linear-gradient(135deg, primary, accent);
  --shadow-glow: 0 0 40px hsl(var(--primary) / 0.3);
  --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

## 🎨 COLOR SYSTEM METHODOLOGY

### Step 1: Brand Analysis & Color Psychology
Analyze using this framework:
- What does this brand/app represent?
- What emotions should users feel?
- What industry/domain conventions exist?
- Who is the target audience?

**Color Psychology Reference:**
- Red: Energy, urgency, passion, danger
- Blue: Trust, professionalism, calm, technology
- Purple: Creativity, luxury, innovation, magic
- Green: Growth, nature, success, health
- Orange: Enthusiasm, warmth, creativity, fun
- Yellow: Optimism, happiness, attention, caution
- Black/Dark: Premium, sophisticated, modern
- White/Light: Clean, minimal, pure, medical

### Step 2: Color Harmony Selection
Choose ONE harmony type:

**Complementary:** Opposite colors (high contrast)
- Primary: 220° (blue) → Accent: 40° (orange)

**Analogous:** Adjacent colors (harmonious)  
- Primary: 220° (blue) → Accent: 190° (cyan)

**Triadic:** 120° apart (balanced)
- Primary: 220° → Accent1: 340° → Accent2: 100°

**Monochromatic:** Same hue, different saturation/lightness
- Primary: 220° 91% 55% → Accent: 220° 91% 75%

## ✨ ANIMATION & EFFECTS SYSTEM

Define four animation categories:

1. **ENTRANCE ANIMATIONS**
```css
@keyframes fade-in-up {
  0% { opacity: 0; transform: translateY(30px) }
  100% { opacity: 1; transform: translateY(0) }
}
```

2. **HOVER/INTERACTION EFFECTS**
```css
.hover-scale { 
  @apply transition-transform duration-200 hover:scale-105 
}
```

3. **AMBIENT ANIMATIONS** (subtle, continuous)
```css
@keyframes float {
  0%, 100% { transform: translateY(0px) }
  50% { transform: translateY(-10px) }
}
```

4. **ATTENTION-GRABBING** (sparingly used)
```css
@keyframes glow {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.5 }
}
```

## 🏗️ COMPONENT VARIANT STRATEGY

Create systematic component variants:

```tsx
const buttonVariants = cva("base-classes", {
  variants: {
    variant: {
      default: "bg-primary text-primary-foreground",
      hero: "bg-gradient-primary hover:shadow-glow hover:scale-105",
      accent: "bg-accent hover:shadow-accent",
      ghost: "hover:bg-accent/10",
      outline: "border-primary text-primary hover:bg-primary/10",
      destructive: "bg-destructive text-destructive-foreground"
    }
  }
})
```

## 📐 SPACING & TYPOGRAPHY SYSTEM

### Consistent Spacing Scale (8px base unit)
```css
gap-2: 8px    /* Tight elements */
gap-4: 16px   /* Default spacing */
gap-6: 24px   /* Card padding */
gap-8: 32px   /* Section elements */
py-12: 48px   /* Small sections */
py-16: 64px   /* Medium sections */
py-24: 96px   /* Large sections */
```

### Typography Hierarchy (Mobile-first)
```css
text-sm     → text-base    /* Body text */
text-lg     → text-xl      /* Subheadings */
text-2xl    → text-4xl     /* Section headings */
text-4xl    → text-6xl     /* Page headings */
text-5xl    → text-7xl     /* Hero headings */
```

## 🎯 PROJECT ADAPTATION WORKFLOW

Execute this systematic approach:

### Step 1: Discovery & Analysis (5 minutes)
1. Identify project type and industry context
2. Define target audience and technical proficiency
3. Establish brand personality traits
4. Research industry design conventions

### Step 2: Color Palette Creation (10 minutes)
1. Choose primary color based on brand psychology
2. Select appropriate harmony type
3. Calculate accent colors using color theory
4. Define neutral grays for backgrounds/text
5. Create semantic tokens in index.css

### Step 3: Design System Setup (15 minutes)
1. Update index.css with color tokens
2. Create gradients and effect tokens
3. Update tailwind.config.ts with semantic references
4. Define animation keyframes
5. Plan component variants needed

### Step 4: Component Enhancement (ongoing)
1. Enhance components with project-specific variants
2. Never use className overrides - always extend variants
3. Test dark/light mode compatibility
4. Ensure WCAG AA accessibility compliance

## 🚀 QUALITY CHECKLIST

Validate against these standards:

### Design System Compliance
- [ ] No direct colors in components (use semantic tokens)
- [ ] All gradients defined in CSS variables
- [ ] Component variants created instead of overrides
- [ ] Consistent spacing using 8px system
- [ ] Typography hierarchy maintained

### Visual Polish
- [ ] WCAG AA contrast ratios (4.5:1 minimum)
- [ ] Consistent border radius usage
- [ ] Shadow system applied consistently
- [ ] Hover states on all interactive elements
- [ ] Loading and error states designed

### Performance & Accessibility
- [ ] Animations use transform/opacity only
- [ ] prefers-reduced-motion respected
- [ ] Semantic HTML structure
- [ ] Focus states clearly visible
- [ ] Alt text for all images

## 🎨 INDUSTRY-SPECIFIC ADAPTATIONS

Apply these patterns based on project type:

**SaaS Applications**
- Colors: Blues/purples for trust + innovation
- Style: Clean, professional, subtle animations
- Focus: Clear feature benefits, pricing clarity

**E-commerce**
- Colors: Brand-driven, high contrast for CTAs
- Style: Image-heavy, clear product focus
- Focus: Product presentation, easy checkout flow

**Healthcare/Medical**
- Colors: Blues/greens for trust + health
- Style: Clean, accessible, minimal animations
- Focus: Trust-building, clear information hierarchy

**Finance/Fintech**
- Colors: Blues/greys for trust + stability
- Style: Data-heavy, clean charts/graphs
- Focus: Security, reliability, clear metrics

OUTPUT REQUIREMENTS:
1. Complete semantic token system (index.css)
2. Tailwind configuration with semantic references
3. Component variant definitions using cva
4. Animation keyframe library with performance optimization
5. Responsive breakpoint strategy
6. Color psychology explanation for chosen palette
7. Implementation guidelines preventing common mistakes
8. Quality assurance checklist
9. Industry-specific adaptations and considerations

Please analyze my project context and create a design system that reflects the appropriate brand personality while maintaining universal usability principles and systematic scalability.
```

## Example Usage

**Input:**
```
Project type: B2B SaaS analytics platform
Target audience: Data analysts and business intelligence professionals
Brand personality: Professional, trustworthy, innovative, data-driven
Industry: Business intelligence and data analytics
```

## Sample Results

The prompt would generate:
1. **Semantic Token System**: Complete HSL-based color architecture with blue primary (trust/tech) and complementary orange accent
2. **Component Variants**: Professional button library with subtle hover effects and clear hierarchy
3. **Animation Library**: Performance-optimized micro-interactions focused on data visualization feedback
4. **Typography Scale**: Clean, readable hierarchy optimized for data-heavy interfaces
5. **Responsive Strategy**: Dashboard-optimized layouts with mobile considerations
6. **Quality Checklist**: Specific validation criteria for B2B professional applications
7. **Implementation Rules**: Detailed guidelines preventing design system violations

## Advanced Features

### Systematic Color Theory Application
- Automatic harmony calculations based on brand psychology
- Industry-appropriate color selections
- Accessibility-compliant contrast ratios built-in

### Component Architecture
- Variant-based system preventing style overrides
- Consistent naming conventions across all components
- Extensible patterns for project-specific needs

### Performance Optimization
- GPU-accelerated animations using transform/opacity
- Semantic token architecture for minimal CSS bundle size
- Mobile-first responsive implementation

### Universal Scalability
- Works across any industry or project type
- Systematic approach ensuring consistency
- Long-term maintainability through semantic tokens

## Notes

- This methodology creates design systems that rival professional design agencies
- Every design decision is systematic and purposeful
- Focus on semantic tokens prevents design drift over time
- Component variants ensure consistency while allowing flexibility
- Quality checklist ensures professional standards are maintained