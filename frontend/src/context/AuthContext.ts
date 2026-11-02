/**
 * CampusFix Authentication Context Definition and useAuth Hook
 */

import { createContext, useContext } from 'react';
import type { User, UserCreatePayload, UserLoginPayload } from '../types';

export interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: UserLoginPayload) => Promise<User>;
  register: (data: UserCreatePayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
