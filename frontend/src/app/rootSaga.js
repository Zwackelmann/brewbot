import { all } from 'redux-saga/effects';
import { watchFetchPorts, watchInitPort } from '../features/ports/sagas';

export default function* rootSaga() {
  yield all([watchFetchPorts(), watchInitPort()]);
}