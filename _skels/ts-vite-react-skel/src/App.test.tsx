import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(document.body).toBeInTheDocument();
  });

  it('renders Vite + React heading', () => {
    render(<App />);
    expect(screen.getByText(/Vite \+ React/)).toBeInTheDocument();
  });

  it('increments counter on button click', () => {
    render(<App />);
    const button = screen.getByRole('button', { name: /count/i });
    expect(button).toHaveTextContent('count is 0');
    fireEvent.click(button);
    expect(button).toHaveTextContent('count is 1');
    fireEvent.click(button);
    expect(button).toHaveTextContent('count is 2');
  });
});
