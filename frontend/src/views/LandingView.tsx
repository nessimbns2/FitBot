import { ArrowRight, ChartNoAxesCombined, Dumbbell, MessageSquare, Salad, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './LandingView.css';

const features = [
  { name: 'Profile', icon: UserRound, text: 'Set your goals, activity level and preferences. Give your plan a starting point that is yours.' },
  { name: 'Nutrition', icon: Salad, text: 'Explore calorie and macro targets, find meal ideas and keep a daily food log.' },
  { name: 'Workouts', icon: Dumbbell, text: 'Build a routine around your schedule and record your training as you go.' },
  { name: 'Progress', icon: ChartNoAxesCombined, text: 'Track your weight and habits over time. See what is working and adjust your next step.' },
  { name: 'AI Coach', icon: MessageSquare, text: 'Ask training and nutrition questions, with guidance grounded in a knowledge base and linked sources.' },
];

export function LandingView() {
  const { isAuthenticated, isLoading } = useAuth();
  const destination = isAuthenticated ? '/dashboard' : '/register';
  const action = isAuthenticated ? 'Open dashboard' : 'Create account';

  return (
    <div className="landing-page">
      <a className="landing-skip" href="#landing-main">Skip to content</a>
      <header className="landing-header">
        <Link className="landing-brand" to="/" aria-label="FitBot home"><span aria-hidden="true">F</span>FitBot</Link>
        <nav aria-label="Main navigation">
          <a className="landing-nav-info" href="#how-it-works">How it works</a>
          {!isAuthenticated && <Link to="/login">Log in</Link>}
          <Link className="landing-button landing-button-small" to={destination} aria-busy={isLoading}>{action}<ArrowRight size={16} aria-hidden="true" /></Link>
        </nav>
      </header>

      <main id="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <p className="landing-kicker">YOUR FITNESS &amp; NUTRITION COACH</p>
          <h1 id="landing-title">One profile. One plan.<br /><span>Progress you can track.</span></h1>
          <p className="landing-intro">Bring your nutrition, workouts and progress together.<br className="landing-desktop-break" /> Build your routine with FitBot, one day at a time.</p>
          <div className="landing-actions">
            <Link className="landing-button" to={destination}>{action}<ArrowRight size={19} aria-hidden="true" /></Link>
            <a className="landing-secondary" href="#how-it-works">See how it works</a>
          </div>
          <ul className="landing-pills" aria-label="Explore FitBot features">
            {features.map(({ name, icon: Icon }, index) => <li key={name}><a href={`#feature-${index}`}><Icon size={16} aria-hidden="true" />{name}</a></li>)}
          </ul>
          <p className="landing-account-note">Your plan and logs, saved to your account.</p>
        </section>

        <section className="landing-section" id="how-it-works" aria-labelledby="landing-steps-title">
          <div className="landing-section-heading"><p>Make a start</p><h2 id="landing-steps-title">A routine that starts with you.</h2></div>
          <ol className="landing-steps">
            <li><span>01</span><h3>Tell us about yourself</h3><p>Create your account and complete your profile with your goals and training preferences.</p></li>
            <li><span>02</span><h3>Put your plan into action</h3><p>Review your nutrition targets, build your workout routine and log your daily activity.</p></li>
            <li><span>03</span><h3>Keep moving forward</h3><p>Follow your progress and ask the AI coach when you need help with your next step.</p></li>
          </ol>
        </section>

        <section className="landing-section landing-features" aria-labelledby="landing-features-title">
          <div className="landing-section-heading"><p>Everything in one place</p><h2 id="landing-features-title">From your first goal to your daily habits.</h2></div>
          <div className="landing-feature-list">{features.map(({ name, icon: Icon, text }, index) => (
            <article id={`feature-${index}`} key={name}><Icon size={25} aria-hidden="true" /><h3>{name}</h3><p>{text}</p></article>
          ))}</div>
        </section>

        <section className="landing-closing" aria-labelledby="landing-ready-title">
          <h2 id="landing-ready-title">Your next step starts here.</h2>
          <Link className="landing-button" to={destination}>{action}<ArrowRight size={18} aria-hidden="true" /></Link>
        </section>
      </main>
      <footer className="landing-footer"><Link className="landing-brand" to="/">FitBot</Link><p>Educational fitness and nutrition guidance. Not a substitute for medical advice.</p><a href="#landing-main">Back to top ↑</a></footer>
    </div>
  );
}
