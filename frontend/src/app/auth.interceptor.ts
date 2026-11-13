import { inject } from '@angular/core';
import { HttpInterceptorFn } from '@angular/common/http';
import { from, switchMap } from 'rxjs';
import { API_BASE_URL } from './api.service';
import { AuthService } from './auth.service';
import { AudienceService } from './audience.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (!request.url.startsWith(API_BASE_URL)) {
    return next(request);
  }

  const auth = inject(AuthService);
  if (!auth.authenticated()) return next(request);
  const audience = inject(AudienceService);
  return from(auth.accessToken()).pipe(
    switchMap(token => {
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (auth.demoMode) headers['X-Demo-Role'] = audience.mode();
      return next(Object.keys(headers).length ? request.clone({ setHeaders: headers }) : request);
    }),
  );
};
