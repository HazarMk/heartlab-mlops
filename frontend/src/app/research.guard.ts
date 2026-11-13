import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AudienceService } from './audience.service';

export const researcherOnly: CanActivateFn = () => {
  const audience = inject(AudienceService);
  return audience.mode() === 'researcher' ? true : inject(Router).parseUrl('/portal');
};
