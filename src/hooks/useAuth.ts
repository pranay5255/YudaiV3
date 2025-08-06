import { useContext } from "react";
import { AuthContext, AuthContextValue } from "../contexts/AuthProvider";

export const useAuth = (): AuthContextValue => {
    const context = useContext(AuthContext);
    if (context === undefined) {
      throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
  };