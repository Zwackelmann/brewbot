import { call, put, takeEvery } from 'redux-saga/effects';
import axios from 'axios';
import api from '../../app/api';
import { fetchRequest, fetchSuccess, fetchFailure, initRequest, initSuccess, initFailure } from './slice';

function* fetchPortsSaga() {
  try {
    const response = yield call(api.listPorts);
    yield put(fetchSuccess(response.ports));
  } catch (error) {
    yield put(fetchFailure(error.message));
  }
}

function* initPortSaga(action) {
  let port = action.payload
  try {
    const response = yield call(
      api.initializePort,
      port
    );
    if (response.status === 'success') {
      yield put(initSuccess({ port: port, response: response }));
    } else {
      yield put(initFailure({ port: port, error: "Initialization Failed" }));
    }
  } catch (error) {
    yield put(initFailure( { port: port, error: error.message } ));
  }
}

export function* watchFetchPorts() {
  yield takeEvery(fetchRequest.type, fetchPortsSaga);
}

export function* watchInitPort() {
  yield takeEvery(initRequest.type, initPortSaga);
}
